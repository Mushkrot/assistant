#!/bin/bash
set -e

echo "=== Realtime Copilot Setup ==="
echo

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Python 3 is required"; exit 1; }

# Create virtual environment
echo "Creating virtual environment..."
cd server
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

cd ..

# Check Node.js
echo
echo "Checking Node.js version..."
node --version || { echo "Node.js is required for the client"; exit 1; }

# Install client dependencies
echo "Installing client dependencies..."
cd client
npm install

echo
echo "=== Setup Complete ==="
echo
echo "Next steps:"
echo "1. Ensure /opt/secure-configs/.env exists and contains OPENAI_API_KEY"
echo "2. Run ./scripts/dev.sh to start the development server"
