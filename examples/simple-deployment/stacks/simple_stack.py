"""
Simple example of deploying Athenaeum using the infra constructs.

This is a minimal example showing how to use Athenaeum's reusable
infrastructure constructs to deploy your own knowledge base.
"""
from pathlib import Path
from aws_cdk import (
    Stack,
    CfnOutput,
)
from constructs import Construct
from athenaeum.infra import DependenciesLayerConstruct, MCPServerConstruct


class SimpleAtheneumStack(Stack):
    """
    Minimal example stack using Athenaeum's infra constructs.
    
    This shows the recommended pattern for deploying Athenaeum-based
    knowledge bases.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_root = Path(__file__).parent.parent.parent
        athenaeum_root = project_root.parent.parent  # Up to code/, then to athenaeum/
        
        # Create dependencies layer
        # This handles all the complex PyTorch/LlamaIndex installation
        
        # Option 1: Local development (use athenaeum source)
        dependencies = DependenciesLayerConstruct(
            self,
            "Dependencies",
            athenaeum_path=str(athenaeum_root),  # Path to athenaeum repo
        )
        
        # Option 2: Published package (after publishing to PyPI)
        # dependencies = DependenciesLayerConstruct(
        #     self,
        #     "Dependencies",
        #     athenaeum=">=0.1.0,<0.2.0",  # Version constraint
        # )
        
        # Create MCP server
        # This creates Lambda + API Gateway + S3 bucket
        server = MCPServerConstruct(
            self,
            "Server",
            dependencies_layer=dependencies.layer,
            index_path=str(project_root / "index") if (project_root / "index").exists() else None,
            environment={
                # Add your environment variables here
                # For example, if using OpenAI:
                # "OPENAI_API_KEY": "sk-...",  # Better: use Secrets Manager!
            },
        )
        
        # Outputs
        CfnOutput(self, "ApiUrl", value=server.api_url)
