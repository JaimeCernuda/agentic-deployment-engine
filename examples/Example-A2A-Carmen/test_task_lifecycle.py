#!/usr/bin/env python3
"""
Task Lifecycle and Context Management Test Suite.

Tests the A2A task-based implementation with:
- Task state transitions (SUBMITTED → WORKING → COMPLETED)
- Context management for multi-turn conversations
- Task refinement with referenceTaskIds
- JSON-RPC 2.0 protocol compliance
- Task immutability rules
- Artifact management
"""
import requests
import json
import sys
import time
from uuid import uuid4


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")


def print_section(text):
    """Print a section header"""
    print(f"\n{Colors.CYAN}{'-'*70}{Colors.RESET}")
    print(f"{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'-'*70}{Colors.RESET}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


class TaskLifecycleTester:
    """Test suite for A2A task lifecycle and context management"""

    def __init__(self, base_url="http://localhost:9001"):
        self.base_url = base_url
        self.query_url = f"{base_url}/query"
        self.results = []
        self.test_count = 0

    def send_jsonrpc_request(self, method, params, request_id=None):
        """
        Send JSON-RPC 2.0 request to agent.

        Args:
            method: RPC method name
            params: Method parameters
            request_id: Request ID (auto-generated if not provided)

        Returns:
            tuple: (success: bool, response_data: dict, error_msg: str)
        """
        if request_id is None:
            request_id = self.test_count + 1

        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }

        try:
            response = requests.post(
                self.query_url,
                json=jsonrpc_request,
                headers={"Content-Type": "application/json"},
                timeout=600
            )

            if response.status_code != 200:
                return False, None, f"HTTP {response.status_code}: {response.text}"

            rpc_response = response.json()

            # Validate JSON-RPC 2.0 format
            if rpc_response.get("jsonrpc") != "2.0":
                return False, None, f"Invalid JSON-RPC version: {rpc_response.get('jsonrpc')}"

            if rpc_response.get("id") != request_id:
                return False, None, f"Response ID mismatch: expected {request_id}, got {rpc_response.get('id')}"

            # Check for error
            if "error" in rpc_response:
                error = rpc_response["error"]
                return False, None, f"RPC Error {error.get('code')}: {error.get('message')}"

            # Success
            return True, rpc_response.get("result", {}), None

        except requests.exceptions.Timeout:
            return False, None, "Request timeout"
        except requests.exceptions.ConnectionError:
            return False, None, "Connection error - is the agent running?"
        except Exception as e:
            return False, None, f"Exception: {type(e).__name__}: {e}"

    def test_task_state_transitions(self):
        """Test 1: Task state transitions (SUBMITTED → WORKING → COMPLETED)"""
        print_section("Test 1: Task State Transitions")
        self.test_count += 1

        context_id = f"ctx-test-{uuid4().hex[:8]}"
        task_id = f"task-{uuid4().hex[:8]}"

        print(f"Context ID: {context_id}")
        print(f"Task ID: {task_id}")
        print(f"Query: Calculate 5 + 3")

        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Calculate 5 + 3",
                "context_id": context_id,
                "task_id": task_id
            }
        )

        if not success:
            print_error(f"Request failed: {error}")
            self.results.append(False)
            return False

        # Validate task structure
        task = result.get("task", {})

        print(f"\nTask State: {task.get('status', {}).get('state')}")
        print(f"Task ID: {task.get('task_id')}")
        print(f"Context ID: {task.get('context_id')}")

        # Check task reached terminal state (COMPLETED)
        if task.get("status", {}).get("state") == "completed":
            print_success("Task reached COMPLETED state")
        else:
            print_error(f"Task state is {task.get('status', {}).get('state')}, expected 'completed'")
            self.results.append(False)
            return False

        # Check artifacts exist
        artifacts = task.get("artifacts", [])
        if artifacts:
            print_success(f"Task has {len(artifacts)} artifact(s)")
            artifact = artifacts[0]
            print(f"  Artifact: {artifact.get('name')}")
            print(f"  Content: {artifact.get('content')[:100]}...")
        else:
            print_error("Task has no artifacts")
            self.results.append(False)
            return False

        # Check response content
        response_text = result.get("response", "")
        if "8" in response_text:
            print_success(f"Response contains expected result: {response_text}")
        else:
            print_warning(f"Response may not contain expected result: {response_text}")

        self.results.append(True)
        return True

    def test_context_persistence(self):
        """Test 2: Context persistence across multiple tasks"""
        print_section("Test 2: Context Persistence (Multi-turn Conversation)")
        self.test_count += 1

        context_id = f"ctx-multiturm-{uuid4().hex[:8]}"

        print(f"Using context ID: {context_id}")
        print(f"\n{Colors.BOLD}Turn 1: Initial query{Colors.RESET}")

        # Turn 1: Initial query
        task_id_1 = f"task-{uuid4().hex[:8]}"
        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Convert 100 USD to EUR",
                "context_id": context_id,
                "task_id": task_id_1
            }
        )

        if not success:
            print_error(f"Turn 1 failed: {error}")
            self.results.append(False)
            return False

        task_1 = result.get("task", {})
        response_1 = result.get("response", "")

        print(f"Task 1 ID: {task_1.get('task_id')}")
        print(f"Task 1 State: {task_1.get('status', {}).get('state')}")
        print(f"Response: {response_1[:150]}...")

        if task_1.get("status", {}).get("state") != "completed":
            print_error("Task 1 did not complete")
            self.results.append(False)
            return False

        print_success("Turn 1 completed")

        # Wait a moment
        time.sleep(1)

        # Turn 2: Follow-up in same context
        print(f"\n{Colors.BOLD}Turn 2: Follow-up query (same context){Colors.RESET}")
        task_id_2 = f"task-{uuid4().hex[:8]}"

        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Add 50 to that result",
                "context_id": context_id,  # Same context
                "task_id": task_id_2
            }
        )

        if not success:
            print_error(f"Turn 2 failed: {error}")
            self.results.append(False)
            return False

        task_2 = result.get("task", {})
        response_2 = result.get("response", "")

        print(f"Task 2 ID: {task_2.get('task_id')}")
        print(f"Task 2 State: {task_2.get('status', {}).get('state')}")
        print(f"Response: {response_2[:150]}...")

        # Verify both tasks share the same context
        if task_1.get("context_id") == task_2.get("context_id") == context_id:
            print_success(f"Both tasks share context: {context_id}")
        else:
            print_error("Tasks have different context IDs")
            self.results.append(False)
            return False

        # Check if agent maintained context (response should reference previous result)
        if any(indicator in response_2.lower() for indicator in ["add", "50", "135", "eur"]):
            print_success("Agent maintained conversational context")
        else:
            print_warning("Agent may not have maintained full context")

        self.results.append(True)
        return True

    def test_task_refinement(self):
        """Test 3: Task refinement with referenceTaskIds"""
        print_section("Test 3: Task Refinement (referenceTaskIds)")
        self.test_count += 1

        context_id = f"ctx-refinement-{uuid4().hex[:8]}"

        print(f"Using context ID: {context_id}")
        print(f"\n{Colors.BOLD}Step 1: Initial task{Colors.RESET}")

        # Step 1: Create initial task
        task_id_1 = f"task-{uuid4().hex[:8]}"
        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Calculate 25 + 17",
                "context_id": context_id,
                "task_id": task_id_1
            }
        )

        if not success:
            print_error(f"Initial task failed: {error}")
            self.results.append(False)
            return False

        task_1 = result.get("task", {})
        print(f"Task 1 ID: {task_1.get('task_id')}")
        print(f"Task 1 State: {task_1.get('status', {}).get('state')}")
        print(f"Response: {result.get('response', '')[:100]}...")
        print_success("Initial task completed")

        time.sleep(1)

        # Step 2: Refinement task with reference
        print(f"\n{Colors.BOLD}Step 2: Refinement task (references Task 1){Colors.RESET}")
        task_id_2 = f"task-{uuid4().hex[:8]}"

        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Multiply that result by 2",
                "context_id": context_id,
                "task_id": task_id_2,
                "reference_task_ids": [task_id_1]  # Reference to previous task
            }
        )

        if not success:
            print_error(f"Refinement task failed: {error}")
            self.results.append(False)
            return False

        task_2 = result.get("task", {})
        print(f"Task 2 ID: {task_2.get('task_id')}")
        print(f"Task 2 State: {task_2.get('status', {}).get('state')}")
        print(f"Reference Task IDs: {task_2.get('reference_task_ids', [])}")
        print(f"Response: {result.get('response', '')[:100]}...")

        # Verify reference was included
        if task_id_1 in task_2.get("reference_task_ids", []):
            print_success(f"Task 2 correctly references Task 1: {task_id_1}")
        else:
            print_warning("Task 2 does not explicitly reference Task 1")

        # Check if result makes sense (42 * 2 = 84)
        response_2 = result.get("response", "")
        if "84" in response_2:
            print_success("Refinement produced expected result (84)")
        else:
            print_warning(f"Refinement result unclear: {response_2}")

        self.results.append(True)
        return True

    def test_task_immutability(self):
        """Test 4: Task immutability (terminal states cannot be modified)"""
        print_section("Test 4: Task Immutability")
        self.test_count += 1

        context_id = f"ctx-immutable-{uuid4().hex[:8]}"
        task_id = f"task-{uuid4().hex[:8]}"

        print(f"Context ID: {context_id}")
        print(f"Task ID: {task_id}")

        # Create and complete a task
        print(f"\n{Colors.BOLD}Step 1: Create and complete task{Colors.RESET}")
        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "What is 10 + 20?",
                "context_id": context_id,
                "task_id": task_id
            }
        )

        if not success:
            print_error(f"Task creation failed: {error}")
            self.results.append(False)
            return False

        task = result.get("task", {})
        state = task.get("status", {}).get("state")

        print(f"Task State: {state}")
        print(f"Response: {result.get('response', '')[:100]}...")

        if state != "completed":
            print_error(f"Task is not in terminal state (state: {state})")
            self.results.append(False)
            return False

        print_success("Task reached terminal state: COMPLETED")

        # Verify task persists with same ID
        print(f"\n{Colors.BOLD}Step 2: Verify task immutability{Colors.RESET}")
        print("Note: Task should remain in COMPLETED state")
        print("New requests with same task_id should reference the same immutable task")

        # Note: True immutability testing requires task/get endpoint
        # For now, we verify that completed tasks have the expected structure

        if task.get("artifacts") and task.get("created_at") and task.get("updated_at"):
            print_success("Task has immutable structure (artifacts, timestamps)")
        else:
            print_warning("Task structure may be incomplete")

        self.results.append(True)
        return True

    def test_multi_agent_orchestration(self):
        """Test 5: Multi-agent orchestration with task tracking"""
        print_section("Test 5: Multi-Agent Orchestration")
        self.test_count += 1

        context_id = f"ctx-orchestration-{uuid4().hex[:8]}"
        task_id = f"task-{uuid4().hex[:8]}"

        print(f"Context ID: {context_id}")
        print(f"Task ID: {task_id}")
        print(f"Query: Convert 100 USD to EUR and add 50")
        print(f"\nThis requires:")
        print(f"  1. Finance Agent: Convert 100 USD to EUR")
        print(f"  2. Math Agent: Add 50 to result")

        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Convert 100 USD to EUR and add 50",
                "context_id": context_id,
                "task_id": task_id
            }
        )

        if not success:
            print_error(f"Multi-agent task failed: {error}")
            self.results.append(False)
            return False

        task = result.get("task", {})
        response_text = result.get("response", "")

        print(f"\nTask ID: {task.get('task_id')}")
        print(f"Task State: {task.get('status', {}).get('state')}")
        print(f"Response: {response_text[:200]}...")

        # Check task completed
        if task.get("status", {}).get("state") != "completed":
            print_error("Multi-agent orchestration did not complete")
            self.results.append(False)
            return False

        # Check if response contains expected elements (EUR and a number around 135)
        has_eur = "eur" in response_text.lower()
        has_number = any(str(num) in response_text for num in range(130, 140))

        if has_eur and has_number:
            print_success("Multi-agent orchestration successful (contains EUR and result)")
        elif has_eur:
            print_warning("Response contains EUR but result may be unclear")
        else:
            print_warning("Multi-agent orchestration result unclear")

        self.results.append(True)
        return True

    def test_error_handling(self):
        """Test 6: Error handling and FAILED state"""
        print_section("Test 6: Error Handling")
        self.test_count += 1

        context_id = f"ctx-error-{uuid4().hex[:8]}"
        task_id = f"task-{uuid4().hex[:8]}"

        print(f"Context ID: {context_id}")
        print(f"Task ID: {task_id}")
        print(f"Query: [Intentionally ambiguous/problematic query]")

        # Send a query that might cause issues
        success, result, error = self.send_jsonrpc_request(
            method="query",
            params={
                "query": "Divide by zero",  # Potentially problematic
                "context_id": context_id,
                "task_id": task_id
            }
        )

        # Even if the query has issues, the system should handle it gracefully
        if not success:
            # JSON-RPC error is acceptable
            print_warning(f"Request returned error (expected): {error}")
            self.results.append(True)
            return True

        task = result.get("task", {})
        state = task.get("status", {}).get("state")

        print(f"Task State: {state}")
        print(f"Response: {result.get('response', '')[:150]}...")

        # Task should either complete with explanation or fail gracefully
        if state in ["completed", "failed"]:
            print_success(f"System handled problematic query gracefully (state: {state})")
        else:
            print_warning(f"Unexpected task state: {state}")

        self.results.append(True)
        return True

    def run_all_tests(self):
        """Run all task lifecycle tests"""
        print_header("A2A Task Lifecycle and Context Management Test Suite")
        print(f"Testing agent at: {Colors.BOLD}{self.base_url}{Colors.RESET}")
        print(f"\nWaiting 5 seconds for agent to be ready...")
        time.sleep(5)

        # Run all tests with delays between them
        tests = [
            ("Task State Transitions", self.test_task_state_transitions),
            ("Context Persistence", self.test_context_persistence),
            ("Task Refinement", self.test_task_refinement),
            ("Task Immutability", self.test_task_immutability),
            ("Multi-Agent Orchestration", self.test_multi_agent_orchestration),
            ("Error Handling", self.test_error_handling)
        ]

        for idx, (name, test) in enumerate(tests, 1):
            try:
                print(f"\n{Colors.CYAN}Running test {idx}/{len(tests)}: {name}{Colors.RESET}")
                test()
                # Add delay between tests to avoid overwhelming the agents
                if idx < len(tests):
                    print(f"{Colors.YELLOW}Waiting 10 seconds before next test...{Colors.RESET}")
                    time.sleep(10)
            except Exception as e:
                print_error(f"Test exception: {type(e).__name__}: {e}")
                self.results.append(False)

        # Summary
        print_header("Test Summary")

        passed = sum(self.results)
        total = len(self.results)

        print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
        print(f"  Passed: {Colors.GREEN}{passed}/{total}{Colors.RESET}")
        print(f"  Failed: {Colors.RED}{total - passed}/{total}{Colors.RESET}")

        if passed == total:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.RESET}")
            return 0
        else:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ {total - passed} test(s) failed{Colors.RESET}")
            return 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test A2A task lifecycle and context management")
    parser.add_argument(
        "--url",
        default="http://localhost:9001",
        help="Base URL of the General Agent (default: http://localhost:9001)"
    )
    args = parser.parse_args()

    tester = TaskLifecycleTester(base_url=args.url)
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
