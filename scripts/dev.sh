#!/bin/bash

# Start both server and client in development mode
# Run from project root directory

echo "=== Starting Realtime Copilot Development Server ==="
echo

# Check if secure env exists
if [ ! -f /opt/secure-configs/.env ]; then
    echo "Error: /opt/secure-configs/.env file not found."
    echo "Create it on the server and add OPENAI_API_KEY (and optionally OLLAMA_* settings)."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo
    echo "Shutting down..."
    kill $SERVER_PID 2>/dev/null
    kill $CLIENT_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start server
echo "Starting Python server..."
cd server
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
cd ..

# Wait for server to start
sleep 2

# Start client
echo "Starting React client..."
cd client
npm run dev &
CLIENT_PID=$!
cd ..

echo
echo "=== Development servers running ==="
echo "Server: http://localhost:8000"
echo "Client: http://localhost:3000"
echo
echo "Press Ctrl+C to stop"

# Wait for both processes
wait
