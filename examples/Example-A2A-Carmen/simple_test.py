#!/usr/bin/env python3
"""Simple test to verify General Agent works with requests library"""
import requests
import json

url = "http://localhost:9001/query"
payload = {
    "jsonrpc": "2.0",
    "method": "query",
    "params": {
        "query": "Calculate 5 + 3",
        "context_id": "ctx-simple-test",
        "task_id": "task-simple-test"
    },
    "id": 1
}

print("Sending request to General Agent...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)

    print(f"\nStatus code: {response.status_code}")
    print(f"Response received!")

    rpc_response = response.json()
    print(f"\nParsed JSON:")
    print(json.dumps(rpc_response, indent=2))

    if rpc_response.get("result"):
        task = rpc_response["result"].get("task", {})
        print(f"\n✓ Task state: {task.get('status', {}).get('state')}")
        print(f"✓ Response: {rpc_response['result'].get('response', '')}")
    else:
        print(f"\n✗ No result in response")

except requests.exceptions.Timeout:
    print(f"\n✗ Request timed out after 120 seconds")
except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
