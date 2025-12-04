"""
DependenciesLayerConstruct - A reusable Lambda layer for Athenaeum dependencies.

This construct creates a Lambda layer containing:
- LlamaIndex (core, OpenAI integrations, FAISS)
- FAISS CPU
- FastAPI, Uvicorn, Pydantic
- All other Athenaeum dependencies

NO PyTorch or HuggingFace transformers - uses OpenAI API for embeddings and chat.
This keeps the layer well under the 250MB unzipped limit.
"""
from pathlib import Path
from typing import Optional
from aws_cdk import (
    Duration,
    aws_lambda as lambda_,
)
from constructs import Construct


class DependenciesLayerConstruct(Construct):
    """
    Lambda layer containing Athenaeum and its dependencies (no PyTorch).
    
    Uses OpenAI API for embeddings and chat, so no local models needed.
    This keeps the layer size well under Lambda's 250MB unzipped limit.
    
    Example (local development):
        ```python
        deps_layer = DependenciesLayerConstruct(
            self, "Deps",
            athenaeum_path="/path/to/athenaeum",
            requirements_path="path/to/requirements.txt",
        )
        
        # Use in your Lambda function
        my_function = lambda_.Function(
            self, "MyFunc",
            layers=[deps_layer.layer],
            ...
        )
        ```
    
    Example (published package):
        ```python
        deps_layer = DependenciesLayerConstruct(
            self, "Deps",
            athenaeum=">=0.1.0,<0.2.0",  # From PyPI
            requirements_path="path/to/requirements.txt",
        )
        ```
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        athenaeum: Optional[str] = None,
        athenaeum_path: Optional[str] = None,
        requirements_path: Optional[str] = None,
        description: str = "Athenaeum dependencies (LlamaIndex, FAISS, FastAPI)",
    ) -> None:
        """
        Create a dependencies layer for Athenaeum.
        
        Args:
            scope: CDK scope
            construct_id: Construct ID
            athenaeum: Install athenaeum from PyPI/git (e.g., ">=0.1.0" or "@git+https://...")
            athenaeum_path: Install athenaeum from local source (for development)
            requirements_path: Additional requirements file to install
            description: Layer description
            
        Note: Specify EITHER athenaeum OR athenaeum_path, not both.
        """
        super().__init__(scope, construct_id)
        
        # Validation: must specify exactly one
        if athenaeum and athenaeum_path:
            raise ValueError(
                "Specify either 'athenaeum' (for PyPI/git) or 'athenaeum_path' (for local dev), not both"
            )
        if not athenaeum and not athenaeum_path:
            raise ValueError(
                "Must specify either 'athenaeum' (version/URL for PyPI/git) or 'athenaeum_path' (path for local dev)"
            )
        
        # Determine installation method and asset path
        if athenaeum:
            # Published: install from PyPI or git
            athenaeum_install_cmd = f"pip install --no-cache-dir 'athenaeum{athenaeum}' -t /asset-output/python"
            # Use current directory as asset path (minimal context)
            asset_path = str(Path(__file__).parent)
        else:
            # Local dev: install from source
            athenaeum_install_cmd = "pip install --no-cache-dir /asset-input -t /asset-output/python"
            asset_path = athenaeum_path
        
        # Build bundling commands - simple pip install, no PyTorch complexity
        bundling_commands = []
        
        # Add requirements installation
        if requirements_path:
            bundling_commands.append(
                f"pip install --no-cache-dir -r /asset-input/{requirements_path} -t /asset-output/python"
            )
        
        # Install athenaeum package (which pulls in all dependencies via pyproject.toml)
        bundling_commands.append(athenaeum_install_cmd)
        
        # Cleanup to reduce layer size
        bundling_commands.extend([
            # Remove Python cache and dist-info
            "rm -rf /asset-output/python/**/__pycache__",
            "rm -rf /asset-output/python/*.dist-info",
            # Remove test/example/doc directories from all packages
            "find /asset-output/python -type d -name tests -exec rm -rf {} + 2>/dev/null || true",
            "find /asset-output/python -type d -name test -exec rm -rf {} + 2>/dev/null || true",
            "find /asset-output/python -type d -name testing -exec rm -rf {} + 2>/dev/null || true",
            "find /asset-output/python -type d -name examples -exec rm -rf {} + 2>/dev/null || true",
            "find /asset-output/python -type d -name docs -exec rm -rf {} + 2>/dev/null || true",
            # Remove .pyi stub files (type hints not needed at runtime)
            "find /asset-output/python -name '*.pyi' -delete 2>/dev/null || true",
        ])
        
        # Create the layer
        self.layer = lambda_.LayerVersion(
            self,
            "Layer",
            code=lambda_.Code.from_asset(
                asset_path,
                exclude=[
                    "**/__pycache__",
                    "**/*.pyc",
                    "**/tests",
                    "**/.venv",
                    "**/cdk.out",
                    "**/.git",
                    "**/*.md",
                    "**/docs",
                ],
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_12.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        " && ".join(bundling_commands),
                    ],
                },
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description=description,
        )
