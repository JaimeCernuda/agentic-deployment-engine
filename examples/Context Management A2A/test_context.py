"""
Context Management Test Script

This script provides utilities to test the two scenarios for evaluating
A2A native context management:

Scenario 1 - Long text in prompt:
    - User sends a very long text with irrelevant information ("filler")
    - The user's name appears only once within the text
    - After one or more unrelated turns, the user asks: "What is my name?"

Scenario 2 - Name inside a file:
    - User uploads a file (txt, md, or pdf) containing only their name
    - The name is NOT mentioned in the prompt text
    - After one or more unrelated turns, the user asks: "What is my name?"

Objective:
    Evaluate what information remains accessible in the agent's active context
    in each scenario, without forcing retention, prioritization, or summarization.

IMPORTANT: This test uses context_id to maintain conversation continuity
following the A2A protocol specification.
"""

import requests
import json
import time
import uuid
from pathlib import Path


AGENT_URL = "http://localhost:9010"


def send_query(
    query: str,
    context_id: str = None,
    task_id: str = None,
    files: list = None
) -> dict:
    """
    Send a query to the context test agent with A2A context management.

    Args:
        query: The query text
        context_id: Optional context_id to continue a conversation
        task_id: Optional task_id (usually auto-generated)
        files: Optional list of file attachments, each with:
               - file_name: str
               - file_content: str
               - mime_type: str (optional, defaults to "text/plain")

    Returns:
        Response dict with 'response', 'context_id', 'task_id', and 'task'
    """
    payload = {
        "query": query,
        "context_id": context_id,
        "task_id": task_id
    }

    if files:
        payload["files"] = files

    try:
        response = requests.post(
            f"{AGENT_URL}/query",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending query: {e}")
        return {"error": str(e)}


def get_context_info(context_id: str) -> dict:
    """Get information about a context (tasks, messages, etc.)."""
    try:
        response = requests.get(
            f"{AGENT_URL}/context/{context_id}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting context: {e}")
        return {"error": str(e)}


def generate_filler_text(paragraphs: int = 50) -> str:
    """Generate filler text with irrelevant information."""
    filler_topics = [
        "The weather today has been quite variable with occasional sunshine breaking through the clouds. "
        "Many people enjoy spending time outdoors when the conditions are favorable. "
        "The local park has been particularly busy with families and joggers alike.",

        "Technology continues to evolve at an unprecedented pace. New smartphones are released every year "
        "with improved cameras and faster processors. The integration of artificial intelligence into "
        "daily applications has transformed how we interact with our devices.",

        "Cooking has become a popular hobby for many people during recent years. From simple recipes "
        "to gourmet dishes, the variety of cuisines available to explore is endless. Online tutorials "
        "and cooking shows have made it easier than ever to learn new techniques.",

        "The history of ancient civilizations continues to fascinate researchers and enthusiasts alike. "
        "Archaeological discoveries provide new insights into how our ancestors lived, worked, and "
        "built societies that laid the foundations for modern civilization.",

        "Sports bring communities together and promote physical health and wellbeing. Whether it's "
        "team sports like football and basketball, or individual pursuits like running and swimming, "
        "regular physical activity has numerous benefits for both body and mind.",

        "Music has the power to evoke emotions and create lasting memories. From classical symphonies "
        "to modern pop hits, the diversity of musical genres reflects the rich tapestry of human "
        "creativity and cultural expression across different societies and eras.",

        "Environmental conservation has become increasingly important in recent decades. Efforts to "
        "protect endangered species, reduce pollution, and combat climate change require collective "
        "action from governments, businesses, and individuals around the world.",

        "Literature offers windows into different worlds, perspectives, and experiences. Whether "
        "through fiction or non-fiction, books have the power to educate, entertain, and inspire "
        "readers of all ages. Libraries remain important community resources for access to knowledge.",

        "Travel broadens the mind and exposes us to different cultures and ways of life. Exploring "
        "new places, trying local cuisines, and meeting people from diverse backgrounds can be "
        "transformative experiences that foster understanding and appreciation.",

        "The study of astronomy reveals the vastness of the universe and our place within it. "
        "From distant galaxies to nearby planets, the cosmos continues to inspire wonder and drive "
        "scientific exploration through advanced telescopes and space missions."
    ]

    text_blocks = []
    for i in range(paragraphs):
        text_blocks.append(filler_topics[i % len(filler_topics)])

    return "\n\n".join(text_blocks)


def scenario_1_long_text(user_name: str = "Carmen"):
    """
    Scenario 1: Long text with name embedded.

    The user's name appears once within a very long text with irrelevant info.
    Then, after unrelated interactions in DIFFERENT contexts, the user returns
    to the original context and asks "What is my name?"

    Flow:
    1. Context A: User sends long text with name embedded
    2. Context B: Unrelated question (different context)
    3. Context C: Another unrelated question (different context)
    4. Context A: User asks "What is my name?" (back to original context)
    """
    print("\n" + "="*70)
    print("SCENARIO 1: Long text in prompt with embedded name")
    print("="*70)

    # Generate unique context_ids
    context_id_main = f"ctx-main-{uuid.uuid4().hex[:8]}"
    context_id_unrelated_1 = f"ctx-unrelated1-{uuid.uuid4().hex[:8]}"
    context_id_unrelated_2 = f"ctx-unrelated2-{uuid.uuid4().hex[:8]}"

    print(f"\nMain Context ID: {context_id_main}")
    print(f"Unrelated Context 1: {context_id_unrelated_1}")
    print(f"Unrelated Context 2: {context_id_unrelated_2}")

    # Generate long filler text
    filler = generate_filler_text(paragraphs=30)

    # Insert the name somewhere in the middle
    paragraphs = filler.split("\n\n")
    middle_index = len(paragraphs) // 2
    name_sentence = f"By the way, my name is {user_name}."
    paragraphs[middle_index] = paragraphs[middle_index] + f" {name_sentence}"
    long_text = "\n\n".join(paragraphs)

    print(f"\n[STEP 1] Sending long text ({len(long_text)} chars) with name '{user_name}' embedded...")
    print(f"         Name appears in paragraph {middle_index + 1} of {len(paragraphs)}")
    print(f"         Context: {context_id_main}")

    response1 = send_query(
        query=f"Please read the following text carefully:\n\n{long_text}\n\nPlease acknowledge that you have received this text.",
        context_id=context_id_main
    )
    print(f"\nTask ID: {response1.get('task_id')}")
    print(f"Agent response: {response1.get('response', str(response1))[:500]}...")

    # Unrelated interaction 1 - DIFFERENT context_id
    print("\n[STEP 2] Sending unrelated query (DIFFERENT context)...")
    print(f"         Context: {context_id_unrelated_1}")
    time.sleep(2)
    response2 = send_query(
        query="What is the capital of France?",
        context_id=context_id_unrelated_1  # Different context!
    )
    print(f"\nTask ID: {response2.get('task_id')}")
    print(f"Agent response: {response2.get('response', str(response2))}")

    # Unrelated interaction 2 - DIFFERENT context_id
    print("\n[STEP 3] Sending another unrelated query (DIFFERENT context)...")
    print(f"         Context: {context_id_unrelated_2}")
    time.sleep(2)
    response3 = send_query(
        query="How many planets are in our solar system?",
        context_id=context_id_unrelated_2  # Different context!
    )
    print(f"\nTask ID: {response3.get('task_id')}")
    print(f"Agent response: {response3.get('response', str(response3))}")

    # Critical question - BACK TO ORIGINAL context_id
    print("\n[STEP 4] Asking: 'What is my name?' (BACK TO ORIGINAL context)...")
    print(f"         Context: {context_id_main}")
    time.sleep(2)
    response4 = send_query(
        query="What is my name?",
        context_id=context_id_main  # Back to original context!
    )
    print(f"\nTask ID: {response4.get('task_id')}")
    print(f"Agent response: {response4.get('response', str(response4))}")

    # Show context info for main context
    print("\n[INFO] Main context summary:")
    context_info = get_context_info(context_id_main)
    print(f"  - Total tasks: {context_info.get('task_count', 'N/A')}")
    print(f"  - Total messages: {context_info.get('message_count', 'N/A')}")

    print("\n" + "-"*70)
    print("SCENARIO 1 RESULT:")
    print(f"Main Context ID: {context_id_main}")
    print(f"Expected name: {user_name}")
    final_response = response4.get('response', '')
    name_recalled = user_name.lower() in final_response.lower()
    print(f"Agent could {'RECALL' if name_recalled else 'NOT recall'} the name")
    print("-"*70)

    return {
        "scenario": 1,
        "context_id": context_id_main,
        "user_name": user_name,
        "text_length": len(long_text),
        "final_response": final_response,
        "name_recalled": name_recalled,
        "total_tasks": context_info.get('task_count', 0),
        "total_messages": context_info.get('message_count', 0)
    }


def scenario_2_file_attachment(user_name: str = "Carmen", file_type: str = "txt"):
    """
    Scenario 2: Name inside a file.

    The user uploads a file containing only their name (NOT in the prompt text).
    The file is sent as a proper A2A file attachment, not embedded in the query.
    Then, after unrelated interactions in DIFFERENT contexts, the user returns
    to the original context and asks "What is my name?"

    Flow:
    1. Context A: User sends file with name (name NOT in prompt text)
    2. Context B: Unrelated question (different context)
    3. Context C: Another unrelated question (different context)
    4. Context A: User asks "What is my name?" (back to original context)
    """
    print("\n" + "="*70)
    print("SCENARIO 2: Name inside a file (real file attachment)")
    print("="*70)

    # Generate unique context_ids
    context_id_main = f"ctx-file-{uuid.uuid4().hex[:8]}"
    context_id_unrelated_1 = f"ctx-unrelated1-{uuid.uuid4().hex[:8]}"
    context_id_unrelated_2 = f"ctx-unrelated2-{uuid.uuid4().hex[:8]}"

    print(f"\nMain Context ID: {context_id_main}")
    print(f"Unrelated Context 1: {context_id_unrelated_1}")
    print(f"Unrelated Context 2: {context_id_unrelated_2}")

    # Create a test file locally that the agent can read with MCP tools
    test_file = Path(__file__).parent / f"test_name_file.{file_type}"
    test_file.write_text(user_name)
    print(f"[SETUP] Created test file: {test_file} with content: '{user_name}'")

    # Get absolute path for the agent to read
    file_absolute_path = str(test_file.absolute())
    file_name = test_file.name

    # Send query asking agent to read the file - NO name in the query text!
    print(f"\n[STEP 1] Asking agent to read file (name NOT in prompt text)...")
    print(f"         File: {file_name}")
    print(f"         Path: {file_absolute_path}")
    print(f"         Content: '{user_name}'")
    print(f"         Context: {context_id_main}")

    response1 = send_query(
        query=f"There's information in this file: {file_absolute_path}",
        context_id=context_id_main
    )
    print(f"\nTask ID: {response1.get('task_id')}")
    print(f"Agent response: {response1.get('response', str(response1))}")

    # Unrelated interaction 1 - DIFFERENT context_id
    print("\n[STEP 2] Sending unrelated query (DIFFERENT context)...")
    print(f"         Context: {context_id_unrelated_1}")
    time.sleep(2)
    response2 = send_query(
        query="What year did World War II end?",
        context_id=context_id_unrelated_1  # Different context!
    )
    print(f"\nTask ID: {response2.get('task_id')}")
    print(f"Agent response: {response2.get('response', str(response2))}")

    # Unrelated interaction 2 - DIFFERENT context_id
    print("\n[STEP 3] Sending another unrelated query (DIFFERENT context)...")
    print(f"         Context: {context_id_unrelated_2}")
    time.sleep(2)
    response3 = send_query(
        query="What is the chemical symbol for water?",
        context_id=context_id_unrelated_2  # Different context!
    )
    print(f"\nTask ID: {response3.get('task_id')}")
    print(f"Agent response: {response3.get('response', str(response3))}")

    # Critical question - BACK TO ORIGINAL context_id
    print("\n[STEP 4] Asking: 'What is my name?' (BACK TO ORIGINAL context)...")
    print(f"         Context: {context_id_main}")
    time.sleep(2)
    response4 = send_query(
        query="What is my name?",
        context_id=context_id_main  # Back to original context!
    )
    print(f"\nTask ID: {response4.get('task_id')}")
    print(f"Agent response: {response4.get('response', str(response4))}")

    # Cleanup
    test_file.unlink()
    print(f"\n[CLEANUP] Removed test file: {test_file}")

    # Show context info for main context
    print("\n[INFO] Main context summary:")
    context_info = get_context_info(context_id_main)
    print(f"  - Total tasks: {context_info.get('task_count', 'N/A')}")
    print(f"  - Total messages: {context_info.get('message_count', 'N/A')}")

    print("\n" + "-"*70)
    print("SCENARIO 2 RESULT:")
    print(f"Main Context ID: {context_id_main}")
    print(f"Expected name: {user_name}")
    print(f"File read via MCP tools: {file_name}")
    final_response = response4.get('response', '')
    name_recalled = user_name.lower() in final_response.lower()
    print(f"Agent could {'RECALL' if name_recalled else 'NOT recall'} the name")
    print("-"*70)

    return {
        "scenario": 2,
        "context_id": context_id_main,
        "user_name": user_name,
        "file_type": file_type,
        "file_name": file_name,
        "final_response": final_response,
        "name_recalled": name_recalled,
        "total_tasks": context_info.get('task_count', 0),
        "total_messages": context_info.get('message_count', 0)
    }


def run_all_tests(user_name: str = "Carmen"):
    """Run both test scenarios and summarize results."""
    print("\n" + "="*70)
    print("A2A CONTEXT MANAGEMENT TEST SUITE")
    print("="*70)
    print(f"\nTest user name: {user_name}")
    print(f"Agent URL: {AGENT_URL}")
    print("\nThis test uses context_id to maintain conversation continuity")
    print("following the A2A protocol specification.")

    # Check agent health
    try:
        health = requests.get(f"{AGENT_URL}/health", timeout=5)
        if health.status_code != 200:
            print(f"\n[ERROR] Agent not healthy: {health.status_code}")
            return
        print(f"\n[OK] Agent is healthy")
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Cannot connect to agent: {e}")
        print("Please ensure the agent is running: python run_agents.py")
        return

    results = []

    # Run Scenario 1
    try:
        result1 = scenario_1_long_text(user_name)
        results.append(result1)
    except Exception as e:
        print(f"\n[ERROR] Scenario 1 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append({"scenario": 1, "error": str(e)})

    print("\n\nWaiting 5 seconds before next scenario...\n")
    time.sleep(5)

    # Run Scenario 2
    try:
        result2 = scenario_2_file_attachment(user_name)
        results.append(result2)
    except Exception as e:
        print(f"\n[ERROR] Scenario 2 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append({"scenario": 2, "error": str(e)})

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for result in results:
        scenario = result.get("scenario", "?")
        if "error" in result:
            print(f"\nScenario {scenario}: ERROR - {result['error']}")
        else:
            recalled = result.get("name_recalled", False)
            print(f"\nScenario {scenario}:")
            print(f"  - Context ID: {result.get('context_id', 'N/A')}")
            print(f"  - Tasks created: {result.get('total_tasks', 'N/A')}")
            print(f"  - Messages in context: {result.get('total_messages', 'N/A')}")
            print(f"  - Name recalled: {'YES' if recalled else 'NO'}")
            if not recalled:
                print(f"  - Agent response: {result.get('final_response', 'N/A')[:200]}...")

    print("\n" + "="*70)
    print("END OF TESTS")
    print("="*70)

    return results


def interactive_test():
    """Interactive test mode - send custom queries with context management."""
    print("\n" + "="*70)
    print("INTERACTIVE TEST MODE (with A2A context management)")
    print("="*70)
    print("\nCommands:")
    print("  /new       - Start a new context (new conversation)")
    print("  /context   - Show current context info")
    print("  /quit      - Exit interactive mode")
    print(f"\nAgent URL: {AGENT_URL}")

    context_id = None

    while True:
        try:
            query = input("\nYou: ").strip()

            if query.lower() == '/quit':
                print("Exiting interactive mode.")
                break

            if query.lower() == '/new':
                context_id = None
                print("Started new context. Next message will create a new context_id.")
                continue

            if query.lower() == '/context':
                if context_id:
                    info = get_context_info(context_id)
                    print(f"\nContext ID: {context_id}")
                    print(f"Tasks: {info.get('task_count', 'N/A')}")
                    print(f"Messages: {info.get('message_count', 'N/A')}")
                else:
                    print("\nNo context active. Send a message to create one.")
                continue

            if not query:
                continue

            response = send_query(query, context_id=context_id)

            # Update context_id from response
            if 'context_id' in response:
                if context_id is None:
                    print(f"[New context created: {response['context_id']}]")
                context_id = response['context_id']

            print(f"\nAgent: {response.get('response', str(response))}")

        except KeyboardInterrupt:
            print("\n\nExiting interactive mode.")
            break


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test A2A context management")
    parser.add_argument(
        "--mode",
        choices=["all", "scenario1", "scenario2", "interactive"],
        default="all",
        help="Test mode: all (both scenarios), scenario1, scenario2, or interactive"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Carmen",
        help="User name to use in tests (default: Carmen)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:9010",
        help="Agent URL (default: http://localhost:9010)"
    )

    args = parser.parse_args()
    AGENT_URL = args.url

    if args.mode == "all":
        run_all_tests(args.name)
    elif args.mode == "scenario1":
        scenario_1_long_text(args.name)
    elif args.mode == "scenario2":
        scenario_2_file_attachment(args.name)
    elif args.mode == "interactive":
        interactive_test()
