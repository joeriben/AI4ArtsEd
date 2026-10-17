#!/usr/bin/env python3
"""
Test Auto-Media Orchestration: Interception-Pipeline → Auto-Media → Output-Pipeline
Tests dada.json (Interception) → auto starts → sd35_large (Output)
"""
import requests
import json
import time

# Test parameters
SERVER_URL = "http://localhost:17801"
ENDPOINT = f"{SERVER_URL}/api/schema/pipeline/execute"

def test_auto_media():
    """Test Auto-Media orchestration with dada config"""

    print("=" * 80)
    print("TEST: Auto-Media Orchestration (dada → sd35_large)")
    print("=" * 80)

    # Request payload
    payload = {
        "schema": "dada",
        "input_text": "A red bicycle",
    }

    print(f"\nRequest to: {ENDPOINT}")
    print(f"Schema: {payload['schema']}")
    print(f"Input: {payload['input_text']}")
    print("\nSending request...")

    start_time = time.time()

    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120  # 2 minute timeout
        )

        elapsed = time.time() - start_time

        print(f"\nResponse Status: {response.status_code}")
        print(f"Elapsed Time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()

            print("\n" + "=" * 80)
            print("RESULT")
            print("=" * 80)

            print(f"\nStatus: {data.get('status')}")

            # Interception Pipeline Output
            print("\n--- Text Transformation (Interception-Pipeline) ---")
            print(f"Config: {data.get('schema')}")
            print(f"Steps: {data.get('steps_completed')}")
            print(f"Time: {data.get('execution_time'):.2f}s")
            print(f"\nTransformed Text:")
            print(data.get('final_output', 'N/A')[:500])
            if len(data.get('final_output', '')) > 500:
                print("...")

            # Media Output
            if 'media_output' in data:
                print("\n--- Media Generation (Output-Pipeline) ---")
                media = data['media_output']

                if 'error' in media:
                    print(f"Status: ERROR")
                    print(f"Error: {media['error']}")
                elif 'status' in media and media['status'] == 'not_available':
                    print(f"Status: NOT AVAILABLE")
                    print(f"Message: {media['message']}")
                else:
                    print(f"Config: {media.get('config')}")
                    print(f"Media Type: {media.get('media_type')}")
                    print(f"Time: {media.get('execution_time', 0):.2f}s")
                    print(f"\nMedia Output:")
                    print(f"  {media.get('output')}")

                    if media.get('metadata'):
                        print(f"\nMedia Metadata:")
                        for key, value in media['metadata'].items():
                            if key not in ['workflow', 'context']:
                                print(f"  {key}: {value}")
            else:
                print("\n--- No Media Output ---")
                print("(Config did not request media generation)")

            print("\n" + "=" * 80)

            # Success check
            if data.get('status') == 'success':
                print("✓ TEST PASSED: Auto-Media orchestration successful")

                if 'media_output' in data and 'output' in data['media_output']:
                    print(f"✓ Media generated: {data['media_output']['output']}")

                    # Check if it's a ComfyUI prompt_id (UUID format)
                    output = data['media_output']['output']
                    if '-' in output and len(output) == 36:
                        print("✓ ComfyUI workflow submitted (prompt_id format)")
            else:
                print("✗ TEST FAILED")

            print("=" * 80)

        else:
            print(f"\n✗ HTTP Error {response.status_code}")
            print(response.text)

    except requests.exceptions.Timeout:
        print("\n✗ Request timeout (120s)")
    except requests.exceptions.ConnectionError:
        print("\n✗ Connection error - Is the server running?")
        print(f"   Start with: python server.py")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_auto_media()
