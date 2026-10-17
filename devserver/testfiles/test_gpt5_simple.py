"""Simple direct test of GPT-5 Image API"""
import asyncio
import aiohttp
import json
from pathlib import Path

async def test_direct_api():
    """Test OpenRouter GPT-5 Image API directly"""

    # Load API key
    key_file = Path(__file__).parent / "openrouter.key"
    api_key = key_file.read_text().strip()

    print(f"API Key: {api_key[:10]}...")

    # Build request
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai4artsed.com",
        "X-Title": "AI4ArtsEd DevServer"
    }

    payload = {
        "model": "openai/gpt-5-image",
        "messages": [
            {
                "role": "system",
                "content": "You are an AI assistant that generates images. When asked to create an image, generate it directly without additional commentary."
            },
            {
                "role": "user",
                "content": "A serene mountain landscape at sunset"
            }
        ],
        "max_tokens": 4096
    }

    print("\n📤 Sending request...")
    print(f"URL: {url}")
    print(f"Model: {payload['model']}")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            print(f"\n📥 Response Status: {response.status}")

            if response.status == 200:
                data = await response.json()
                print(f"\n✅ Response received")
                print("\n📋 Full Response Structure:")
                print(json.dumps(data, indent=2))
            else:
                error = await response.text()
                print(f"\n❌ Error: {error}")

if __name__ == "__main__":
    asyncio.run(test_direct_api())
