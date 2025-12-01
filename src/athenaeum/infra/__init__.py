"""
AWS CDK infrastructure constructs for Athenaeum.

This package provides reusable L3 constructs for deploying Athenaeum-based
knowledge bases to AWS Lambda.
"""
from .dependencies_layer import DependenciesLayerConstruct
from .mcp_server import MCPServerConstruct

__all__ = [
    "DependenciesLayerConstruct",
    "MCPServerConstruct",
]
