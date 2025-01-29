#!/bin/bash

# Test configuration
TEST_DURATION="30s"   # Test for 30 seconds
NUM_THREADS="2"       # Use 2 threads
NUM_CONNECTIONS="1000" # 200 concurrent connections
PORT="5000"
URL="http://127.0.0.1:8000/"
WRK_COMMAND="wrk -t$NUM_THREADS -c$NUM_CONNECTIONS -d$TEST_DURATION $URL"

# Define the servers to benchmark
declare -A servers
servers["MicroPie"]="uvicorn micro:app --workers 4"
servers["Starlette"]="uvicorn star:app --workers 4"
servers["Quart"]="uvicorn qrt:app --workers 4"
servers["FastAPI"]="uvicorn fast:app --workers 4"

# Output file
RESULTS_FILE="benchmark_results.txt"
echo "=== Benchmark Results ===" > "$RESULTS_FILE"

# Function to start server, run benchmark, and stop server
benchmark_server() {
    local name="$1"
    local command="$2"

    echo -e "\n=== Benchmarking $name ==="
    echo -e "\n=== $name ===" >> "$RESULTS_FILE"

    # Start the server in the background
    eval "$command &"
    SERVER_PID=$!

    # Give the server some time to start
    sleep 3

    # Run wrk test
    WRK_OUTPUT=$(eval "$WRK_COMMAND")

    # Print and save results
    echo "$WRK_OUTPUT"
    echo "$WRK_OUTPUT" >> "$RESULTS_FILE"
    echo -e "\n========================================\n" >> "$RESULTS_FILE"

    # Stop the server
    kill $SERVER_PID
    wait $SERVER_PID 2>/dev/null
}

# Run benchmarks for each server
for name in "${!servers[@]}"; do
    benchmark_server "$name" "${servers[$name]}"
done

echo -e "\nBenchmarking complete. Results saved in $RESULTS_FILE"

