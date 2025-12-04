"""
MCPServerContainerConstruct - Lambda container image-based MCP server deployment.

This construct creates:
- Lambda function using Docker container images (supports PyTorch, up to 10GB)
- API Gateway REST API with CORS support
- S3 bucket for storing the vector index
- Proper IAM roles and permissions

This is the recommended deployment method for Athenaeum as it supports the full
dependency stack including PyTorch and sentence-transformers for embeddings.
"""
from pathlib import Path
from typing import Optional, List
from aws_cdk import (
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as ecr_assets,
)
from constructs import Construct


class MCPServerContainerConstruct(Construct):
    """
    Complete MCP server deployment using Lambda container images.
    
    This construct sets up everything needed to run an Athenaeum MCP server:
    - FastAPI Lambda function in Docker container (supports PyTorch)
    - REST API with CORS
    - S3 bucket for the vector index
    - Environment variables for configuration
    - CloudWatch logs
    
    Container images support up to 10GB, allowing PyTorch and all ML dependencies.
    
    Example:
        ```python
        from athenaeum.infra import MCPServerContainerConstruct
        
        # Create MCP server with container
        server = MCPServerContainerConstruct(
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
        dockerfile_path: Optional[str] = None,
        docker_build_context: Optional[str] = None,
        index_path: Optional[str] = None,
        environment: Optional[dict] = None,
        memory_size: int = 2048,
        ephemeral_storage_size: int = 512,
        timeout: Duration = Duration.minutes(5),
        log_retention: logs.RetentionDays = logs.RetentionDays.ONE_WEEK,
        cors_allow_origins: List[str] = ["*"],
        **kwargs,
    ) -> None:
        """
        Create an MCP server deployment using Docker container images.
        
        Args:
            scope: CDK scope
            construct_id: Construct ID
            dockerfile_path: Path to Dockerfile (default: athenaeum/examples/deployment/Dockerfile)
            docker_build_context: Path to Docker build context (default: athenaeum root)
            index_path: Path to vector index directory (creates S3 bucket if provided)
            environment: Environment variables for Lambda
            memory_size: Lambda memory in MB (default: 2048 for ML workloads)
            ephemeral_storage_size: Lambda ephemeral storage in MB (default: 512)
            timeout: Lambda timeout
            log_retention: CloudWatch log retention
            cors_allow_origins: CORS allowed origins
        """
        super().__init__(scope, construct_id, **kwargs)
        
        # Default Dockerfile and build context paths
        if dockerfile_path is None or docker_build_context is None:
            import athenaeum
            athenaeum_root = Path(athenaeum.__file__).parent.parent.parent
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
            ephemeral_storage_size=ephemeral_storage_size,
            timeout=timeout,
            environment=env_vars,
            log_retention=log_retention,
        )
        
        # Grant S3 read permissions if bucket exists
        if self.index_bucket:
            self.index_bucket.grant_read(self.function)
        
        # Create API Gateway
        self.api = apigateway.LambdaRestApi(
            self,
            "Api",
            handler=self.function,
            proxy=True,
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
        
        # Outputs
        self.api_url = self.api.url
        self.function_name = self.function.function_name
