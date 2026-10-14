"""
Quick test script to verify the mock API connection works.
This is simpler than the full agent to help debug connection issues.
"""

import requests

# Test configuration
base_url = "http://localhost:8000"
api_key = "mock-api-key-001"

print("Testing Mock API Server Connection...")
print("=" * 60)

# Test 1: Health check
print("\n1. Testing health endpoint...")
try:
    response = requests.get(f"{base_url}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: List models
print("\n2. Testing /v1/models endpoint...")
try:
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(f"{base_url}/v1/models", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        models = response.json()
        print(f"   Available models: {[m['id'] for m in models['data']]}")
    else:
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Simple chat completion
print("\n3. Testing /v1/chat/completions endpoint...")
try:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "claude",
        "messages": [
            {"role": "user", "content": "Say hello in one word."}
        ],
        "max_tokens": 50
    }
    response = requests.post(
        f"{base_url}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        print(f"   Response: {content}")
    else:
        print(f"   Error: {response.text}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("Test complete!")
