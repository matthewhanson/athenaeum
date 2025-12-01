#!/usr/bin/env python3
"""
Simple Athenaeum deployment example.

This CDK app shows how to use Athenaeum's reusable infrastructure constructs.
"""
import os
from aws_cdk import App, Environment
from stacks.simple_stack import SimpleAtheneumStack

app = App()

# Get environment from context or use defaults
account = os.environ.get("CDK_DEFAULT_ACCOUNT", app.node.try_get_context("account"))
region = os.environ.get("CDK_DEFAULT_REGION", app.node.try_get_context("region") or "us-east-1")

env = Environment(account=account, region=region)

# Deploy using the simple example stack
SimpleAtheneumStack(
    app,
    "SimpleAtheneumStack",
    env=env,
    description="Simple example of Athenaeum MCP server deployment",
)

app.synth()
