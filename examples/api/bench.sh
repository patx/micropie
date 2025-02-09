#!/bin/bash

# Server details
HOST="127.0.0.1"
PORT="8000"

# Test key-value
TEST_KEY="benchmark_key"
TEST_VALUE="benchmark_value"

# Number of threads and connections
THREADS=4
CONNECTIONS=100
DURATION="30s"

echo "Benchmarking SET operation..."
wrk -t$THREADS -c$CONNECTIONS -d$DURATION http://$HOST:$PORT/set/$TEST_KEY/$TEST_VALUE

echo "Benchmarking GET operation..."
wrk -t$THREADS -c$CONNECTIONS -d$DURATION http://$HOST:$PORT/get/$TEST_KEY

