#!/usr/bin/env python3
"""
Test script for the multi-agent A2A system.
Tests both direct tool queries and agent delegation.
"""
import requests
import json
import sys
import time


def test_query(agent_name, url, query, expected_keywords=None):
    """
    Send a test query to an agent and display the response.

    Args:
        agent_name: Name of the agent being tested
        url: Full URL to the agent's /query endpoint
        query: The query string to send
        expected_keywords: Optional list of keywords to check in response
    """
    print(f"\n{'='*60}")
    print(f"Testing {agent_name}")
    print(f"{'='*60}")
    print(f"Query: {query}")
    print("-" * 60)

    try:
        response = requests.post(
            url,
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=300  # Increased to 5 minutes for slow Claude responses
        )

        if response.status_code == 200:
            result = response.json()
            agent_response = result.get("response", "No response")

            print(f"Status: ✓ SUCCESS (200)")
            print(f"Response:\n{agent_response}")

            # Check for expected keywords
            if expected_keywords:
                found = [kw for kw in expected_keywords if kw.lower() in agent_response.lower()]
                missing = [kw for kw in expected_keywords if kw.lower() not in agent_response.lower()]

                if found:
                    print(f"\n✓ Found expected keywords: {', '.join(found)}")
                if missing:
                    print(f"⚠ Missing keywords: {', '.join(missing)}")

            return True
        else:
            print(f"Status: ✗ FAILED ({response.status_code})")
            print(f"Error: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"Status: ✗ TIMEOUT")
        print("The request took too long. The agent might be processing...")
        return False
    except requests.exceptions.ConnectionError:
        print(f"Status: ✗ CONNECTION ERROR")
        print("Could not connect to the agent. Is it running?")
        return False
    except Exception as e:
        print(f"Status: ✗ ERROR")
        print(f"Exception: {type(e).__name__}: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("Multi-Agent A2A System Test Suite")
    print("="*60)

    # Wait a moment to ensure agents are ready
    print("\nWaiting 2 seconds for agents to be ready...")
    time.sleep(2)

    tools_agent_url = "http://localhost:9002/query"
    search_agent_url = "http://localhost:9004/query"
    general_agent_url = "http://localhost:9001/query"

    results = []

    # Test 1: Direct query to Math Agent (math)
    results.append(test_query(
        "Tools Agent - Addition",
        tools_agent_url,
        "What is 5 + 3?",
        expected_keywords=["8"]
    ))

    # Test 2: Direct query to Math Agent (conversion)
    results.append(test_query(
        "Tools Agent - Unit Conversion",
        tools_agent_url,
        "Convert 100 celsius to fahrenheit",
        expected_keywords=["212", "fahrenheit"]
    ))

    # Test 3: General Agent with knowledge question (should NOT delegate)
    results.append(test_query(
        "General Agent - Knowledge Question",
        general_agent_url,
        "Who discovered gravity?",
        expected_keywords=["Newton", "Isaac"]
    ))

    # Test 4: General Agent with math question (SHOULD delegate to Math Agent)
    results.append(test_query(
        "General Agent - Math Delegation",
        general_agent_url,
        "Calculate 25 + 17 for me",
        expected_keywords=["42"]
    ))

    # Test 5: General Agent with conversion (SHOULD delegate to Math Agent)
    results.append(test_query(
        "General Agent - Conversion Delegation",
        general_agent_url,
        "Convert 5000 meters to kilometers",
        expected_keywords=["5", "kilometer"]
    ))

    # Test 6: General Agent with subtraction (SHOULD delegate)
    results.append(test_query(
        "General Agent - Subtraction Delegation",
        general_agent_url,
        "What is 100 - 45?",
        expected_keywords=["55"]
    ))

    # Test 7: General Agent with currency conversion (SHOULD delegate to Finance Agent)
    results.append(test_query(
        "General Agent - Currency Conversion Delegation",
        general_agent_url,
        "Convert 100 USD to EUR",
        expected_keywords=["EUR"]
    ))

    # Test 8: General Agent with percentage change (SHOULD delegate to Finance Agent)
    results.append(test_query(
        "General Agent - Percentage Change Delegation",
        general_agent_url,
        "What is the percentage change from 50 to 75?",
        expected_keywords=["50"]
    ))

    # Test 9: General Agent requiring various agents (Finance + Math)
    results.append(test_query(
        "General Agent - Multi-Agent Orchestration (Finance + Math)",
        general_agent_url,
        "Convert 100 USD to EUR and then add 50 to the result",
        expected_keywords=["EUR", "135"]
    ))

    # Test 10: Direct query to Search Agent (web search)
    results.append(test_query(
        "Search Agent - Web Search",
        search_agent_url,
        "Search for information about Python programming language",
        expected_keywords=["Python"]
    ))

    # Test 11: General Agent with search question (SHOULD delegate to Search Agent)
    results.append(test_query(
        "General Agent - Search Delegation",
        general_agent_url,
        "Search the web for the latest news about artificial intelligence",
        expected_keywords=["artificial", "intelligence"]
    ))

    # Test 12: General Agent multi-agent orchestration including Search Agent
    results.append(test_query(
        "General Agent - Multi-Agent with Search (Search + Tools)",
        general_agent_url,
        "Search for the current temperature in celsius in Madrid and convert it to fahrenheit",
        expected_keywords=["Madrid", "fahrenheit"]
    ))

    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")

    passed = sum(results)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
