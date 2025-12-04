# Dockerfile for Athenaeum Lambda Container
# Supports PyTorch + sentence-transformers for embeddings
# Uses AWS Lambda Python 3.12 base image with Lambda Web Adapter

FROM public.ecr.aws/lambda/python:3.12

# Install Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set working directory
WORKDIR /var/task

# Install CPU-only PyTorch first (largest dependency, benefits from caching)
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Copy and install Python dependencies
COPY examples/deployment/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy athenaeum source code and install package
COPY src/athenaeum /var/task/athenaeum
COPY pyproject.toml /var/task/
RUN pip install --no-cache-dir .

# Copy Lambda handler and startup script
COPY examples/deployment/lambda_handler.py /var/task/
COPY examples/deployment/run.sh /var/task/
RUN chmod +x /var/task/run.sh

# Set Lambda environment
ENV PORT=8080
ENV AWS_LWA_INVOKE_MODE=response_stream

# Lambda Web Adapter will call this script
CMD ["/var/task/run.sh"]
