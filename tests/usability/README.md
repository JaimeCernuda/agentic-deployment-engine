# Usability Tests

These tests deploy real agents and verify they work correctly by parsing logs and outputs.
They serve as both tests AND examples for users.

## Prerequisites

1. **Python 3.11+** with `uv` installed
2. **Claude API key** set in environment:
   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   ```

## Running Tests

```bash
# Run all usability tests
uv run pytest tests/usability/ -v -m usability

# Run specific scenario
uv run pytest tests/usability/test_scenarios.py::test_simple_weather -v

# Run with verbose output
uv run pytest tests/usability/ -v -s
```

## Test Scenarios

### Scenario 1: Simple Weather Query
- **Job**: `jobs/examples/simple-weather.yaml`
- **Pattern**: Hub-and-spoke
- **Query**: "What is the weather in Tokyo?"
- **Expected**: Response contains "Tokyo" and temperature info

### Scenario 2: Maps Distance Query
- **Job**: `jobs/examples/simple-weather.yaml`
- **Pattern**: Hub-and-spoke
- **Query**: "How far is London from Paris?"
- **Expected**: Response contains distance in km/miles

### Scenario 3: Multi-Agent Coordination
- **Job**: `jobs/examples/simple-weather.yaml`
- **Pattern**: Hub-and-spoke
- **Query**: "What's the weather in Tokyo and how far is it from London?"
- **Expected**: Response contains both weather AND distance info

### Scenario 4: Pipeline Processing
- **Job**: `jobs/examples/pipeline.yaml`
- **Pattern**: Pipeline
- **Tests**: Sequential data flow through stages

### Scenario 5: DAG Workflow
- **Job**: `jobs/examples/distributed-dag.yaml`
- **Pattern**: DAG with dependencies
- **Tests**: Parallel execution with proper ordering

## Writing New Scenarios

```python
@pytest.mark.usability
async def test_my_scenario():
    \"\"\"
    Scenario: Description of what this tests
    Job: path/to/job.yaml
    Query: "The query to send"
    Expected: What the response should contain
    \"\"\"
    scenario = UsabilityScenario(
        job_file="jobs/examples/my-job.yaml",
        query="My test query",
        expected_patterns=["pattern1", "pattern2"],
        timeout=60,
    )
    result = await scenario.run()
    assert result.success, result.error
```
