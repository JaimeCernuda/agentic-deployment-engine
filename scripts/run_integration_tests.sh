#!/bin/bash
# Run integration tests with all agents

set -e

echo "============================================================"
echo "Starting All Agents for Integration Tests"
echo "============================================================"

# Kill any existing agents on these ports
echo "Cleaning up existing processes..."
lsof -ti:9000,9001,9002 | xargs kill -9 2>/dev/null || true
sleep 2

# Start all agents in background
echo "Starting Weather Agent (port 9001)..."
uv run weather-agent > logs/weather_agent_test.log 2>&1 &
WEATHER_PID=$!

echo "Starting Maps Agent (port 9002)..."
uv run maps-agent > logs/maps_agent_test.log 2>&1 &
MAPS_PID=$!

echo "Starting Controller Agent (port 9000)..."
uv run controller-agent > logs/controller_agent_test.log 2>&1 &
CONTROLLER_PID=$!

# Wait for agents to start
echo "Waiting for agents to initialize..."
sleep 15

# Check if agents are running
echo "Checking agent health..."
curl -s http://localhost:9001/health | jq . || echo "Weather agent not responding"
curl -s http://localhost:9002/health | jq . || echo "Maps agent not responding"
curl -s http://localhost:9000/health | jq . || echo "Controller agent not responding"

echo ""
echo "============================================================"
echo "Running Integration Tests"
echo "============================================================"

# Run the integration tests
uv run pytest tests/test_integration.py -v --tb=short

TEST_EXIT_CODE=$?

echo ""
echo "============================================================"
echo "Cleaning Up"
echo "============================================================"

# Kill all agents
echo "Stopping agents..."
kill $WEATHER_PID $MAPS_PID $CONTROLLER_PID 2>/dev/null || true
sleep 2

# Force kill if still running
lsof -ti:9000,9001,9002 | xargs kill -9 2>/dev/null || true

echo "Test logs available at:"
echo "  - logs/weather_agent_test.log"
echo "  - logs/maps_agent_test.log"
echo "  - logs/controller_agent_test.log"
echo ""

exit $TEST_EXIT_CODE
