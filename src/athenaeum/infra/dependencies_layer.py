"""
DependenciesLayerConstruct - A reusable Lambda layer for Athenaeum dependencies.

This construct creates a Lambda layer containing:
- PyTorch CPU-only (optimized, no CUDA)
- Transformers
- LlamaIndex
- FAISS CPU
- All other Athenaeum dependencies

The layer is optimized for size (~1.2GB unzipped, ~300-400MB compressed) by:
- Using CPU-only PyTorch wheels
- Removing development files (headers, tests, docs)
- Removing type stubs
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
    Lambda layer containing Athenaeum and all its heavy dependencies.
    
    This construct handles the complex PyTorch CPU-only installation and
    aggressive cleanup to minimize layer size.
    
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
        description: str = "Athenaeum dependencies (PyTorch, LlamaIndex, FAISS, etc.)",
        **kwargs,
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
        super().__init__(scope, construct_id, **kwargs)
        
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
        
        # Build bundling commands
        bundling_commands = [
            # CRITICAL: Set PIP_EXTRA_INDEX_URL to force ALL pip installs to use CPU-only torch
            # This prevents ANY package from installing CUDA torch (7GB+ of NVIDIA libraries)
            "export PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu",
            # Install torch CPU-only FIRST
            "pip install --no-cache-dir torch -t /asset-output/python",
            # Install transformers WITHOUT dependencies to avoid reinstalling torch
            "pip install --no-cache-dir 'transformers>=4.36' --no-deps -t /asset-output/python",
            # Install transformers' dependencies (excluding torch which is already installed)
            "pip install --no-cache-dir huggingface-hub filelock numpy packaging pyyaml regex requests tokenizers safetensors tqdm -t /asset-output/python",
        ]
        
        # Add requirements installation
        if requirements_path:
            bundling_commands.append(
                f"pip install --no-cache-dir -r /asset-input/{requirements_path} -t /asset-output/python"
            )
        else:
            # Install athenaeum's dependencies
            bundling_commands.append(
                "pip install --no-cache-dir llama-index-core llama-index-embeddings-huggingface llama-index-vector-stores-faiss faiss-cpu fastapi uvicorn pydantic boto3 -t /asset-output/python"
            )
        
        # Install athenaeum package itself
        bundling_commands.append(athenaeum_install_cmd)
        
        # Cleanup to reduce layer size
        bundling_commands.extend([
            # Remove Python cache and dist-info
            "rm -rf /asset-output/python/**/__pycache__",
            "rm -rf /asset-output/python/*.dist-info",
            # Remove PyTorch dev files (headers, tests, bins) - saves ~200MB+
            "rm -rf /asset-output/python/torch/include",
            "rm -rf /asset-output/python/torch/bin",
            "rm -rf /asset-output/python/torch/test",
            "rm -rf /asset-output/python/torch/testing",
            "rm -rf /asset-output/python/torch/share",
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
