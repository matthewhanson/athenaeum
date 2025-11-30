"""
AWS CDK Stack for Athenaeum MCP Server deployment.
"""
from pathlib import Path
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct


class AtheneumStack(Stack):
    """
    CDK Stack for deploying Athenaeum as a serverless Lambda function.
    
    Includes:
    - Lambda function with FastAPI + Mangum
    - API Gateway with OAuth authorizer
    - S3 bucket for index files (optional fallback)
    - IAM roles and permissions
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get project root
        project_root = Path(__file__).parent.parent.parent

        # S3 bucket for index files (if they're too large for Lambda layer)
        index_bucket = s3.Bucket(
            self,
            "IndexBucket",
            bucket_name=f"athenaeum-index-{self.account}",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # Deploy index files to S3 if they exist
        index_path = project_root / "index"
        if index_path.exists():
            s3deploy.BucketDeployment(
                self,
                "IndexDeployment",
                sources=[s3deploy.Source.asset(str(index_path))],
                destination_bucket=index_bucket,
                destination_key_prefix="index/",
            )

        # Lambda layer for dependencies
        # Note: Due to Lambda size limits, we create a layer for heavy dependencies
        dependencies_layer = lambda_.LayerVersion(
            self,
            "DependenciesLayer",
            code=lambda_.Code.from_asset(
                str(project_root),
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_12.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        " && ".join([
                            "pip install --no-cache-dir -r requirements.txt -t /asset-output/python",
                            "rm -rf /asset-output/python/**/__pycache__",
                            "rm -rf /asset-output/python/*.dist-info",
                        ]),
                    ],
                },
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Athenaeum dependencies (LlamaIndex, FAISS, etc.)",
        )

        # Lambda function for the MCP server
        mcp_lambda = lambda_.Function(
            self,
            "MCPServerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="lambda_handler.handler",
            code=lambda_.Code.from_asset(
                str(project_root / "deployment"),
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_12.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        " && ".join([
                            "cp -r /asset-input/src /asset-output/",
                            "cp /asset-input/deployment/lambda_handler.py /asset-output/",
                        ]),
                    ],
                },
            ),
            layers=[dependencies_layer],
            timeout=Duration.seconds(30),
            memory_size=2048,  # Increase for large models/indices
            environment={
                "ATHENAEUM_INDEX_BUCKET": index_bucket.bucket_name,
                "ATHENAEUM_INDEX_DIR": "/tmp/index",  # Lambda tmp storage
                "OAUTH_ISSUER": self.node.try_get_context("oauth_issuer") or "",
                "OAUTH_AUDIENCE": self.node.try_get_context("oauth_audience") or "",
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant Lambda access to S3 bucket
        index_bucket.grant_read(mcp_lambda)

        # Lambda authorizer for OAuth
        oauth_authorizer_lambda = lambda_.Function(
            self,
            "OAuthAuthorizer",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="oauth_authorizer.handler",
            code=lambda_.Code.from_asset(str(project_root / "deployment")),
            timeout=Duration.seconds(5),
            environment={
                "OAUTH_ISSUER": self.node.try_get_context("oauth_issuer") or "",
                "OAUTH_AUDIENCE": self.node.try_get_context("oauth_audience") or "",
                "OAUTH_JWKS_URL": self.node.try_get_context("oauth_jwks_url") or "",
            },
        )

        # API Gateway with Lambda authorizer
        authorizer = apigateway.RequestAuthorizer(
            self,
            "OAuthAuthorizer",
            handler=oauth_authorizer_lambda,
            identity_sources=[apigateway.IdentitySource.header("Authorization")],
            results_cache_ttl=Duration.minutes(5),
        )

        # API Gateway REST API
        api = apigateway.LambdaRestApi(
            self,
            "AtheneumAPI",
            handler=mcp_lambda,
            proxy=True,
            default_method_options=apigateway.MethodOptions(
                authorizer=authorizer,
                authorization_type=apigateway.AuthorizationType.CUSTOM,
            ),
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigateway.MethodLoggingLevel.INFO,
            ),
        )

        # Outputs
        CfnOutput(
            self,
            "APIEndpoint",
            value=api.url,
            description="Athenaeum MCP Server API endpoint",
        )

        CfnOutput(
            self,
            "IndexBucketName",
            value=index_bucket.bucket_name,
            description="S3 bucket for index files",
        )
