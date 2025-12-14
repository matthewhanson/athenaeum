"""
APIServerContainerConstruct - Lambda container image-based API server deployment.

This construct creates:
- Lambda function using Docker container images (supports PyTorch, up to 10GB)
- API Gateway REST API with CORS support
- S3 bucket for storing the vector index
- Proper IAM roles and permissions

This is the recommended deployment method for Athenaeum as it supports the full
dependency stack including PyTorch and sentence-transformers for embeddings.
"""

from pathlib import Path

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Size,
)
from aws_cdk import (
    aws_apigateway as apigateway,
)
from aws_cdk import (
    aws_certificatemanager as acm,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as s3deploy,
)
from constructs import Construct


class APIServerContainerConstruct(Construct):
    """
    Complete API server deployment using Lambda container images.

    This construct sets up everything needed to run an Athenaeum API server:
    - FastAPI Lambda function in Docker container (supports PyTorch)
    - REST API with CORS
    - S3 bucket for the vector index
    - Environment variables for configuration
    - CloudWatch logs

    Container images support up to 10GB, allowing PyTorch and all ML dependencies.

    Example:
        ```python
        from athenaeum.infra import APIServerContainerConstruct

        # Create API server with container
        server = APIServerContainerConstruct(
            self, "Server",
            dockerfile_path="/path/to/Dockerfile",
            index_path="/path/to/index",
            environment={
                "OPENAI_API_KEY": "...",
            },
        )

        # Outputs
        CfnOutput(self, "ApiUrl", value=server.api_url)
        ```
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        dockerfile_path: str | None = None,
        docker_build_context: str | None = None,
        index_path: str | None = None,
        environment: dict | None = None,
        memory_size: int = 2048,
        ephemeral_storage_size: int = 512,
        timeout: Duration = Duration.minutes(5),
        log_retention: logs.RetentionDays = logs.RetentionDays.ONE_WEEK,
        cors_allow_origins: list[str] | None = None,
        custom_domain_name: str | None = None,
        certificate_arn: str | None = None,
        **kwargs,
    ) -> None:
        """
        Create an API server deployment using Docker container images.

        Args:
            scope: CDK scope
            construct_id: Construct ID
            dockerfile_path: Path to Dockerfile (default: athenaeum/examples/deployment/Dockerfile)
            docker_build_context: Path to Docker build context (default: athenaeum root)
            index_path: Path to vector index directory (creates S3 bucket if provided, or None to bake into image)
            environment: Environment variables for Lambda
            memory_size: Lambda memory in MB (recommend 2048+)
            ephemeral_storage_size: Ephemeral storage in MB
            timeout: Lambda timeout
            log_retention: CloudWatch log retention
            cors_allow_origins: CORS allowed origins (default: ["*"])
            custom_domain_name: Optional custom domain name for API Gateway (e.g., "api.example.com")
            certificate_arn: ACM certificate ARN for custom domain (required if custom_domain_name is provided)
        """
        if cors_allow_origins is None:
            cors_allow_origins = ["*"]
        super().__init__(scope, construct_id, **kwargs)

        # Default Dockerfile and build context paths
        if dockerfile_path is None or docker_build_context is None:
            # Try to find athenaeum source directory
            # For file:// installs, look in the installed package's parent directories
            import importlib.metadata

            import athenaeum

            athenaeum_pkg_dir = Path(athenaeum.__file__).parent

            # Try to find the actual source directory
            # Method 1: Check if we're in development (src layout)
            if (
                athenaeum_pkg_dir.parent.name == "src"
                and (athenaeum_pkg_dir.parent.parent / "examples").exists()
            ):
                athenaeum_root = athenaeum_pkg_dir.parent.parent
            # Method 2: Check parent directories for examples/
            elif (athenaeum_pkg_dir.parent / "examples").exists():
                athenaeum_root = athenaeum_pkg_dir.parent
            elif (athenaeum_pkg_dir.parent.parent / "examples").exists():
                athenaeum_root = athenaeum_pkg_dir.parent.parent
            elif (athenaeum_pkg_dir.parent.parent.parent / "examples").exists():
                athenaeum_root = athenaeum_pkg_dir.parent.parent.parent
            # Method 3: Try to get from package metadata (for file:// installs)
            else:
                try:
                    dist = importlib.metadata.distribution("athenaeum")
                    # For file:// installs via uv, check ../../athenaeum from site-packages
                    site_packages = Path(dist._path).parent.parent  # type: ignore[attr-defined]
                    potential_root = site_packages.parent.parent.parent / "athenaeum"
                    if (potential_root / "examples").exists():
                        athenaeum_root = potential_root
                    else:
                        raise RuntimeError("Cannot find athenaeum root with examples/")
                except Exception as e:
                    raise RuntimeError(
                        f"Could not find athenaeum examples directory. "
                        f"Package is at {athenaeum_pkg_dir}. "
                        f"Please provide explicit dockerfile_path and docker_build_context parameters. "
                        f"Error: {e}"
                    ) from e

            if dockerfile_path is None:
                dockerfile_path = str(athenaeum_root / "examples" / "deployment" / "Dockerfile")
            if docker_build_context is None:
                docker_build_context = str(athenaeum_root)

        # Create S3 bucket for index if path provided
        self.index_bucket = None
        if index_path:
            self.index_bucket = s3.Bucket(
                self,
                "IndexBucket",
                removal_policy=RemovalPolicy.RETAIN,
                encryption=s3.BucketEncryption.S3_MANAGED,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            )

            # Deploy index to S3
            s3deploy.BucketDeployment(
                self,
                "IndexDeployment",
                sources=[s3deploy.Source.asset(index_path)],
                destination_bucket=self.index_bucket,
                destination_key_prefix="index/",
            )

        # Prepare environment variables
        env_vars = {
            "PORT": "8080",
            # Enable response streaming for Function URLs with SSE
            # This is required for Lambda Web Adapter to support streaming responses
            "AWS_LWA_INVOKE_MODE": "response_stream",
        }
        if self.index_bucket:
            env_vars["INDEX_BUCKET"] = self.index_bucket.bucket_name
            env_vars["INDEX_KEY"] = "index/"
        if environment:
            env_vars.update(environment)

        # Create Lambda function from Docker image
        self.function = lambda_.DockerImageFunction(
            self,
            "Function",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=docker_build_context,
                file=str(Path(dockerfile_path).relative_to(docker_build_context)),
            ),
            memory_size=memory_size,
            ephemeral_storage_size=Size.mebibytes(ephemeral_storage_size),
            timeout=timeout,
            environment=env_vars,
            log_retention=log_retention,
        )

        # Grant S3 read permissions if bucket exists
        if self.index_bucket:
            self.index_bucket.grant_read(self.function)

        # Create API Gateway for REST endpoints
        self.api = apigateway.LambdaRestApi(
            self,
            "Api",
            handler=self.function,
            proxy=True,
            deploy_options=apigateway.StageOptions(
                stage_name="",  # Use root stage (no /prod prefix) for cleaner URLs
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=cors_allow_origins,
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Api-Key",
                ],
            ),
        )

        # Create Lambda Function URL for SSE endpoint (supports streaming)
        # Function URLs don't have the 30-second timeout limitation of API Gateway
        self.function_url = self.function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=cors_allow_origins,
                allowed_methods=[lambda_.HttpMethod.ALL],
                allowed_headers=["*"],
            ),
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,  # Enable streaming for SSE
        )

        # Set up custom domain if provided
        if custom_domain_name:
            if not certificate_arn:
                raise ValueError(
                    "certificate_arn is required when custom_domain_name is provided"
                )

            # Import the certificate
            certificate = acm.Certificate.from_certificate_arn(
                self, "Certificate", certificate_arn
            )

            # Create custom domain
            domain = apigateway.DomainName(
                self,
                "CustomDomain",
                domain_name=custom_domain_name,
                certificate=certificate,
                endpoint_type=apigateway.EndpointType.EDGE,
            )

            # Map the custom domain to the API with empty base path
            # This maps: custom-domain.com/* -> api-gateway.com/STAGE/*
            # The stage name is "prod" (CDK converts "" to "prod")
            # So we need the API to NOT have /prod in its paths for this to work at root
            domain.add_base_path_mapping(
                self.api,
                base_path="",  # Empty base path = root of custom domain
                stage=self.api.deployment_stage,  # Points to the "prod" stage
            )

            # Store the custom domain and distribution domain name
            self.custom_domain_name = custom_domain_name
            self.distribution_domain_name = domain.domain_name_alias_domain_name
            self.api_url = f"https://{custom_domain_name}"
        else:
            self.custom_domain_name = None
            self.distribution_domain_name = None
            self.api_url = self.api.url

        # Store Function URL for SSE endpoint
        self.sse_url = self.function_url.url

        # Outputs
        self.function_name = self.function.function_name
