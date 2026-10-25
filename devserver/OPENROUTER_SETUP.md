# OpenRouter API Setup

## Quick Setup (2 minutes)

### 1. Get your OpenRouter API key
1. Go to https://openrouter.ai/
2. Sign up or log in
3. Go to "Keys" section
4. Click "Create Key"
5. Copy your API key (starts with `sk-or-v1-...`)

### 2. Create the key file
In the devserver directory, create a file named `openrouter.key`:

```bash
cd <repo>/devserver
nano openrouter.key
```

Paste your API key (just the key, nothing else), save and exit.

**Example file content:**
```
sk-or-v1-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

That's it! The key file is automatically excluded from git.

### 3. Test it works

```bash
python test_gpt5_image.py
```

## What you get

- **Fast cloud image generation** via GPT-5 Image
- Automatically used when you select `execution_mode: fast`
- Cost: ~$0.00004 per image (~4 cents per 1000 images)

## Usage

### Via API
```bash
curl -X POST http://localhost:5000/api/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "dada",
    "input_text": "A mystical forest",
    "execution_mode": "fast"
  }'
```

### Direct config
```bash
curl -X POST http://localhost:5000/api/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "gpt5_image",
    "input_text": "A serene mountain landscape"
  }'
```

## Troubleshooting

**"OpenRouter API key not found"**
- Make sure `openrouter.key` file exists in devserver root
- Check the file contains only your API key (no quotes, no spaces)

**"API error: 401"**
- Your API key is invalid or expired
- Get a new key from https://openrouter.ai/

**"API error: 402"**
- No credits on your OpenRouter account
- Add credits at https://openrouter.ai/credits

## Security

- The `.key` file is excluded from git (in `.gitignore`)
- Never commit API keys to the repository
- Each user needs their own `openrouter.key` file
