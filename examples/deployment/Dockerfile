# Dockerfile for Athenaeum Lambda Container
# Supports PyTorch + sentence-transformers for embeddings
# Uses AWS Lambda Python 3.12 base image with Lambda Web Adapter
#
# Build args allow flexible build context (athenaeum root or parent directory)
# ATHENAEUM_PATH: Path to athenaeum root (default: . for building from athenaeum)
# INDEX_PATH: Path to index directory (default: index)

FROM public.ecr.aws/lambda/python:3.12

# Install Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set working directory
WORKDIR /var/task

# Install CPU-only PyTorch first (largest dependency, benefits from caching)
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Build args for flexible source locations
ARG ATHENAEUM_PATH=.
ARG INDEX_PATH=index

# Copy and install Python dependencies
COPY ${ATHENAEUM_PATH}/examples/deployment/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy athenaeum source code directly (no package install needed)
# All dependencies are already in requirements.txt
COPY ${ATHENAEUM_PATH}/src/athenaeum /var/task/athenaeum

# Copy the index into the image for instant access (no S3 download needed)
COPY ${INDEX_PATH} /var/task/index

# Copy startup script (no lambda_handler.py needed - index is baked in)
COPY ${ATHENAEUM_PATH}/examples/deployment/run.sh /var/task/
RUN chmod +x /var/task/run.sh

# Set Lambda environment
ENV PORT=8080
# Use buffered mode instead of response_stream for API Gateway REST API compatibility
ENV AWS_LWA_INVOKE_MODE=buffered

# Use ENTRYPOINT for the shell script - CMD doesn't work for shell scripts in Lambda
ENTRYPOINT ["/var/task/run.sh"]
