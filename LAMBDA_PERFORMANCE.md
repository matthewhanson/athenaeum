# Lambda Performance Optimization

## Cold Start Analysis

Lambda cold starts with PyTorch and ML models are inherently slow due to:

1. **Container initialization**: ~2-3 seconds (downloading image, starting container)
2. **PyTorch loading**: ~5-8 seconds (importing torch, transformers)
3. **Model loading**: ~2-4 seconds (loading sentence-transformers model)
4. **FAISS index loading**: ~1-2 seconds (loading vector index)

**Total cold start**: 10-17 seconds
**Warm invocation**: 1-2 seconds

## Optimization Strategies

### 1. Provisioned Concurrency (Recommended for Production)

Keep Lambda instances warm 24/7:

```python
# In your CDK stack
from aws_cdk import aws_lambda as lambda_

server_function.add_alias(
    "live",
    provisioned_concurrent_executions=1  # Keep 1 instance always warm
)
```

**Pros:**
- Eliminates cold starts completely
- Consistent sub-2s response times
- Good for production APIs

**Cons:**
- Costs ~$10-15/month for 1 instance (vs $1-2/month on-demand)
- Wastes resources if traffic is sporadic

**Best for:** Production deployments with regular traffic

### 2. Lazy Loading (Implemented, but limited gains)

Load PyTorch/models only when needed:

```python
# Current implementation already does this
def query_index():
    from llama_index.core import load_index_from_storage
    # Only loads when function is called
```

**Gains:** Minimal (~1-2 seconds) because most imports happen at module load time

### 3. Use Lighter Embedding Model

Switch from `all-MiniLM-L6-v2` (90MB) to a smaller model:

```python
# In your indexing command
athenaeum index ./docs \
  --embed-model "sentence-transformers/paraphrase-MiniLM-L3-v2"  # 60MB, faster
```

**Pros:**
- Faster model loading (~1-2 seconds faster)
- Smaller Docker image
- Less memory needed

**Cons:**
- Slightly lower search quality
- Must rebuild index with new model

**Gains:** ~1-2 seconds on cold start

### 4. Increase Memory (Best ROI for Performance)

More memory = faster CPU = faster initialization:

```python
# In nomikos_stack.py
memory_size=4096,  # Up from 2048
```

**Memory → CPU allocation:**
- 2048 MB = ~1 vCPU
- 4096 MB = ~2 vCPUs
- 8192 MB = ~4 vCPUs

**Pros:**
- Faster cold starts (30-40% faster with 4GB vs 2GB)
- Faster query execution
- More headroom for concurrent requests

**Cons:**
- Higher cost per invocation (but still cheap)
- $2-3/month vs $1-2/month for light usage

**Gains:** ~3-5 seconds on cold start

### 5. Pre-Compile Python (Advanced)

Use `python -m compileall` in Dockerfile:

```dockerfile
# Add to Dockerfile after pip install
RUN python -m compileall -b /var/task
```

**Gains:** ~0.5-1 second

### 6. Use Lambda SnapStart (Not Available for Container Images)

SnapStart is only available for .zip deployments, not containers. Our PyTorch dependency requires containers.

### 7. Keep Lambda Warm with Scheduled Events

Ping the endpoint every 5 minutes to keep it warm:

```python
# Add to CDK stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets

# Create a rule to invoke every 5 minutes
rule = events.Rule(
    self, "KeepWarmRule",
    schedule=events.Schedule.rate(Duration.minutes(5)),
)
rule.add_target(targets.LambdaFunction(server_function))
```

**Pros:**
- Free (within Lambda free tier)
- Keeps function warm during business hours

**Cons:**
- Still has cold starts after long idle periods
- Wastes some invocations

**Gains:** Eliminates most cold starts during active hours

### 8. Split into Multiple Functions (Advanced)

Separate heavy ML operations from lightweight API:

- **Function 1** (Fast): Health checks, basic endpoints
- **Function 2** (Heavy): Search/chat with ML models

**Pros:**
- Fast endpoints stay fast
- Can optimize each function separately

**Cons:**
- More complex architecture
- Need to manage multiple functions

## Recommended Configuration

### For Development/Testing (Current)
```python
memory_size=2048
timeout=Duration.minutes(5)
# No provisioned concurrency
```
**Cost:** ~$1-2/month
**Cold start:** 10-17 seconds
**Warm:** 1-2 seconds

### For Production (Moderate Traffic)
```python
memory_size=4096  # Faster CPU
timeout=Duration.minutes(5)
# Add keep-warm event (invoke every 5 min)
```
**Cost:** ~$3-5/month
**Cold start:** 7-12 seconds (rare)
**Warm:** <1 second

### For Production (High Traffic)
```python
memory_size=4096
timeout=Duration.minutes(5)
provisioned_concurrent_executions=1
```
**Cost:** ~$12-15/month
**Cold start:** Never
**Warm:** <1 second

## Alternative: Move to ECS Fargate

If cold starts are unacceptable, consider ECS Fargate:

**Pros:**
- Always warm (container runs continuously)
- Sub-second response times always
- Better for WebSocket/SSE (like MCP)
- Can scale horizontally

**Cons:**
- More expensive (~$20-30/month for always-on)
- More complex setup
- Need load balancer

**When to use:** 
- Production with SLA requirements
- Heavy MCP/SSE usage (GitHub Copilot integration)
- Predictable traffic patterns

## Quick Wins (Implement Today)

1. **Increase memory to 4096 MB** - Best ROI
   ```python
   memory_size=4096
   ```
   
2. **Add keep-warm event** - Free optimization
   ```python
   events.Rule(
       self, "KeepWarmRule",
       schedule=events.Schedule.rate(Duration.minutes(5)),
   ).add_target(targets.LambdaFunction(server_function))
   ```

**Combined effect:** 
- Cold starts drop from 10-17s to 7-12s
- Cold starts become rare (only after 5+ min idle)
- Cost increase: +$2-3/month

## Monitoring Cold Starts

Track cold start frequency:

```bash
# View init duration in CloudWatch
aws logs insights start-query \
  --log-group-name /aws/lambda/YourFunction \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @duration, @initDuration | filter @type = "REPORT" | stats avg(@initDuration) as avg_cold_start'
```

## Summary

| Strategy | Cost Impact | Cold Start Improvement | Effort |
|----------|-------------|------------------------|--------|
| Increase memory (4GB) | +$2/mo | 30-40% faster | 5 min |
| Keep-warm events | $0 | Eliminates 90% | 10 min |
| Lighter model | $0 | 10-15% faster | 30 min |
| Provisioned concurrency | +$10/mo | Eliminates 100% | 5 min |
| ECS Fargate | +$20/mo | Eliminates 100% | 2 hours |

**Recommended:** Start with memory + keep-warm ($2-3/month), evaluate if you need provisioned concurrency later.
