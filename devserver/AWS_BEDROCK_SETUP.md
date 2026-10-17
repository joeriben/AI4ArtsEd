# AWS Bedrock Setup Guide

## Overview

AWS Bedrock integration provides DSGVO-compliant access to Anthropic Claude models via AWS EU region (eu-central-1).

## Features

- ✅ DSGVO-compliant (EU region: eu-central-1)
- ✅ Environment-based credentials (no key files)
- ✅ boto3 SDK with proper AWS authentication
- ✅ Exact Bedrock model IDs

## Setup

### 1. Install boto3

```bash
pip install boto3
```

### 2. Set Environment Variables

**Option A: Use setup script (recommended for development)**

```bash
source devserver/setup_aws_env.sh
```

**Option B: Manual export**

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-central-1"
```

**Option C: Add to shell profile (persistent)**

Add to `~/.bashrc` or `~/.zshrc`:

```bash
source /path/to/ai4artsed_development/devserver/setup_aws_env.sh
```

### 3. Start Server

```bash
# After setting ENV variables:
python3 devserver/app.py
```

## Settings Page

### Provider Options

The Settings Page supports 5 LLM providers:

| Provider | DSGVO | Credentials | Description |
|----------|-------|-------------|-------------|
| `none` | ✅ | - | Local only (Ollama) |
| `bedrock` | ✅ | ENV | AWS Bedrock EU region |
| `anthropic` | ✅ | anthropic.key | Direct Anthropic API |
| `openai` | ❌ | openai.key | Direct OpenAI API (US) |
| `openrouter` | ❌ | openrouter.key | OpenRouter aggregator (US) |

### Hardware Matrix (3 Tiers)

Each VRAM configuration has 3 options:

1. **dsgvo_local**: Only local Ollama models
2. **dsgvo_cloud**: AWS Bedrock EU models (DSGVO ✓)
3. **non_dsgvo**: OpenRouter models (DSGVO ✗)

### Example: 96 GB VRAM Configurations

#### Tier 1: DSGVO Local
```python
"dsgvo_local": {
    "label": "96 GB VRAM (DSGVO, local only)",
    "models": {
        "STAGE2_INTERCEPTION_MODEL": "local/llama3.2-vision:90b",
        ...
    },
    "EXTERNAL_LLM_PROVIDER": "none"
}
```

#### Tier 2: DSGVO Cloud (AWS Bedrock)
```python
"dsgvo_cloud": {
    "label": "96 GB VRAM (DSGVO, AWS Bedrock EU)",
    "models": {
        "STAGE2_INTERCEPTION_MODEL": "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ...
    },
    "EXTERNAL_LLM_PROVIDER": "bedrock"
}
```

#### Tier 3: Non-DSGVO (OpenRouter)
```python
"non_dsgvo": {
    "label": "96 GB VRAM (non-DSGVO, OpenRouter)",
    "models": {
        "STAGE2_INTERCEPTION_MODEL": "openrouter/anthropic/claude-3-5-sonnet",
        ...
    },
    "EXTERNAL_LLM_PROVIDER": "openrouter"
}
```

## Model IDs

### Bedrock Model IDs (Exact format required)

| Model | Bedrock ID |
|-------|------------|
| Claude Haiku 4.5 | `bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Claude Sonnet 4.5 | `bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Claude Opus 4.5 | `bedrock/eu.anthropic.claude-opus-4-5-20251101-v2:0` |

**Important**: Model IDs must be exact! The `eu.` prefix indicates EU region.

## Security Best Practices

### ✅ DO

- Use Environment Variables for credentials
- Use IAM Roles when hosting on AWS (EC2/ECS/Lambda)
- Use AWS Secrets Manager for production
- Rotate keys regularly
- Use least-privilege IAM policies

### ❌ DON'T

- Store keys in files (aws_bedrock.key) - deprecated approach
- Upload keys via Settings Page UI - security risk
- Commit keys to git
- Share keys in plain text
- Use root AWS account credentials

## Production Deployment

### On AWS (Recommended)

Use IAM Roles instead of static keys:

1. **EC2**: Attach IAM role to instance
2. **ECS**: Use task role
3. **Lambda**: Use execution role

boto3 automatically uses the role credentials, no ENV variables needed!

### On-Premise / Docker

**Docker Compose:**

```yaml
services:
  devserver:
    environment:
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_DEFAULT_REGION: eu-central-1
```

**systemd Service:**

```ini
[Service]
Environment="AWS_ACCESS_KEY_ID=..."
Environment="AWS_SECRET_ACCESS_KEY=..."
Environment="AWS_DEFAULT_REGION=eu-central-1"
```

## Troubleshooting

### "boto3 not installed"

```bash
pip install boto3
```

### "Unable to locate credentials"

Ensure ENV variables are set:

```bash
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
echo $AWS_DEFAULT_REGION
```

### "Access Denied" Error

Check IAM permissions. Required policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:eu-central-1::foundation-model/anthropic.claude-*"
    }
  ]
}
```

### Wrong Region

The server must use `eu-central-1` for EU Bedrock models. Check:

```bash
echo $AWS_DEFAULT_REGION  # Should be: eu-central-1
```

## Architecture

```
User Input
    ↓
Settings Page (select: bedrock)
    ↓
user_settings.json
    {
      "EXTERNAL_LLM_PROVIDER": "bedrock",
      "STAGE2_INTERCEPTION_MODEL": "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
    }
    ↓
Backend Router (detects bedrock/ prefix)
    ↓
Prompt Interception Engine
    ↓
_call_aws_bedrock()
    boto3.client("bedrock-runtime", region_name="eu-central-1")
    ↓
AWS Bedrock EU (eu-central-1)
    ↓
Anthropic Claude Model
    ↓
Response
```

## Support

For AWS Bedrock specific issues, check:
- AWS Bedrock Documentation: https://docs.aws.amazon.com/bedrock/
- boto3 Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- AWS IAM Best Practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
