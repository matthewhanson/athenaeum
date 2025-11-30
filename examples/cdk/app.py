#!/usr/bin/env python3
"""
AWS CDK app for deploying Athenaeum MCP server.
"""
import os
from aws_cdk import App, Environment
from stacks.athenaeum_stack import AtheneumStack

app = App()

# Get environment from context or use defaults
account = os.environ.get("CDK_DEFAULT_ACCOUNT", app.node.try_get_context("account"))
region = os.environ.get("CDK_DEFAULT_REGION", app.node.try_get_context("region") or "us-east-1")

env = Environment(account=account, region=region)

# Deploy the Athenaeum stack
AtheneumStack(
    app,
    "AtheneumStack",
    env=env,
    description="Athenaeum MCP Server - RAG system with vector search"
)

app.synth()
