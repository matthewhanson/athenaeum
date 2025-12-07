"""
MCPServerConstruct - A reusable construct for deploying Athenaeum MCP servers.

This construct creates:
- Lambda function running FastAPI via Lambda Web Adapter
- API Gateway REST API with CORS support
- S3 bucket for storing the vector index
- Proper IAM roles and permissions
"""

from pathlib import Path

from aws_cdk import (
    Duration,
    RemovalPolicy,
)
from aws_cdk import (
    aws_apigateway as apigateway,
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


class MCPServerConstruct(Construct):
    """
    Complete MCP server deployment with Lambda, API Gateway, and S3.

    This construct sets up everything needed to run an Athenaeum MCP server:
    - FastAPI Lambda function with Lambda Web Adapter
    - REST API with CORS
    - S3 bucket for the vector index
    - Environment variables for configuration
    - CloudWatch logs

    Example:
        ```python
        from athenaeum.infra import DependenciesLayerConstruct, MCPServerConstruct

        # Create dependencies layer
        deps = DependenciesLayerConstruct(self, "Deps")

        # Create MCP server
        server = MCPServerConstruct(
            self, "Server",
            dependencies_layer=deps.layer,
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
        dependencies_layer: lambda_.ILayerVersion,
        handler_code_path: str | None = None,
        index_path: str | None = None,
        environment: dict | None = None,
        memory_size: int = 1024,
        timeout: Duration = Duration.minutes(5),
        log_retention: logs.RetentionDays = logs.RetentionDays.ONE_WEEK,
        cors_allow_origins: list[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Create an MCP server deployment.

        Args:
            scope: CDK scope
            construct_id: Construct ID
            dependencies_layer: Lambda layer with athenaeum dependencies
            handler_code_path: Path to deployment code (default: athenaeum/examples/deployment)
            index_path: Path to vector index directory (creates S3 bucket if provided)
            environment: Environment variables for Lambda
            memory_size: Lambda memory in MB
            timeout: Lambda timeout
            log_retention: CloudWatch log retention
            cors_allow_origins: CORS allowed origins (default: ["*"])
        """
        if cors_allow_origins is None:
            cors_allow_origins = ["*"]
        super().__init__(scope, construct_id, **kwargs)

        # Default handler code path
        if handler_code_path is None:
            import athenaeum

            athenaeum_root = Path(athenaeum.__file__).parent.parent.parent
            handler_code_path = str(athenaeum_root / "examples" / "deployment")

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

        # Lambda Web Adapter layer (official AWS layer)
        web_adapter_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "WebAdapter",
            # Latest version for us-east-1
            # See: https://github.com/awslabs/aws-lambda-web-adapter
            "arn:aws:lambda:us-east-1:753240598075:layer:LambdaAdapterLayerX86:23",
        )

        # Prepare environment variables
        env_vars = {
            "AWS_LWA_INVOKE_MODE": "response_stream",
            "PORT": "8080",
        }
        if self.index_bucket:
            env_vars["INDEX_BUCKET"] = self.index_bucket.bucket_name
            env_vars["INDEX_KEY"] = "index/"
        if environment:
            env_vars.update(environment)

        # Create Lambda function
        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="run.sh",  # Lambda Web Adapter entry point
            code=lambda_.Code.from_asset(
                handler_code_path,
                exclude=["**/__pycache__", "**/*.pyc"],
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_12.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        " && ".join(
                            [
                                # Copy lambda handler
                                "cp /asset-input/lambda_handler.py /asset-output/",
                                # Create run.sh script for Lambda Web Adapter
                                "echo '#!/bin/sh' > /asset-output/run.sh",
                                "echo 'python lambda_handler.py && exec uvicorn athenaeum.mcp_server:app --host 0.0.0.0 --port 8080' >> /asset-output/run.sh",
                                "chmod +x /asset-output/run.sh",
                            ]
                        ),
                    ],
                },
            ),
            layers=[dependencies_layer, web_adapter_layer],
            memory_size=memory_size,
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
