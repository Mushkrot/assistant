#!/bin/bash
set -e

echo "=== Building Realtime Copilot ==="
echo

# Build client
echo "Building React client..."
cd client
npm run build
cd ..

echo
echo "=== Build Complete ==="
echo "Client built to server/static/"
echo
echo "To run production server:"
echo "  cd server && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8010"
