"""
Simple example of deploying Athenaeum using container-based deployment.

This is a minimal example showing how to use Athenaeum's high-level
MCPServerContainerConstruct to deploy your own knowledge base.
"""
import os
from pathlib import Path
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_logs as logs,
)
from constructs import Construct
from athenaeum.infra import MCPServerContainerConstruct


class SimpleAtheneumStack(Stack):
    """
    Minimal example stack using Athenaeum's container-based deployment.
    
    This shows the recommended pattern for deploying Athenaeum-based
    knowledge bases using Docker containers (supports PyTorch, up to 10GB).
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_root = Path(__file__).parent.parent
        index_path = project_root / "index"
        
        # Create MCP server using container deployment
        # This creates Lambda + API Gateway + S3 bucket + Docker image
        server = MCPServerContainerConstruct(
            self,
            "Server",
            # Index will be uploaded to S3 and downloaded on Lambda cold start
            index_path=str(index_path) if index_path.exists() else None,
            
            # Environment variables for Lambda
            environment={
                # OpenAI API key (required for LLM)
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
                # Or use AWS Bedrock instead (comment out OPENAI_API_KEY above):
                # No API key needed - uses IAM permissions
            },
            
            # Lambda resource configuration
            memory_size=2048,  # 2GB recommended for ML workloads with PyTorch
            ephemeral_storage_size=512,  # /tmp storage for index files
            timeout=Duration.minutes(5),
            
            # Logging configuration
            log_retention=logs.RetentionDays.ONE_WEEK,
            
            # CORS configuration
            cors_allow_origins=["*"],  # TODO: Restrict in production
        )
        
        # Outputs
        CfnOutput(self, "ApiUrl", value=server.api_url)
        CfnOutput(self, "FunctionName", value=server.function_name)
        if server.index_bucket:
            CfnOutput(self, "IndexBucketName", value=server.index_bucket.bucket_name)

