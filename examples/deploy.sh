#!/usr/bin/env bash
# Deployment script for Athenaeum CDK stack

set -e

echo "🚀 Deploying Athenaeum to AWS Lambda..."

# Check for AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ Error: AWS credentials not configured"
    echo "Please run: aws configure"
    exit 1
fi

# Check for CDK context
if [ ! -f cdk.context.json ]; then
    echo "⚠️  Warning: cdk.context.json not found"
    echo "Copy cdk.context.json.example and configure OAuth settings"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install CDK dependencies if needed
echo "📦 Installing CDK dependencies..."
uv sync --extra deploy

# Bootstrap CDK (only needed once per account/region)
echo "🔧 Bootstrapping CDK..."
uv run cdk bootstrap

# Synthesize CloudFormation template
echo "🏗️  Synthesizing stack..."
uv run cdk synth

# Deploy stack
echo "☁️  Deploying to AWS..."
uv run cdk deploy --require-approval never

echo "✅ Deployment complete!"
echo ""
echo "To get your API endpoint:"
echo "  aws cloudformation describe-stacks --stack-name AtheneumStack --query 'Stacks[0].Outputs'"
