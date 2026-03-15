#!/bin/bash
# ================================================================
# ProofGraph — One-command setup
# Run: bash setup.sh
# ================================================================

set -e
echo ""
echo "🔷 ProofGraph Setup"
echo "========================"

# 1. Python venv
if [ ! -d "venv" ]; then
  echo "→ Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate

# 2. Dependencies
echo "→ Installing dependencies..."
pip install -q --upgrade pip
pip install -q fastapi uvicorn python-dotenv aiosqlite pydantic opengradient requests

# 3. .env
if [ ! -f "backend/.env" ]; then
  cp backend/.env.example backend/.env
  echo ""
  echo "⚠️  Created backend/.env from template."
  echo "   Edit backend/.env and add your OG_PRIVATE_KEY before starting."
  echo ""
fi

# 4. Reset DB (optional)
if [ "$1" == "--reset" ]; then
  echo "→ Resetting database..."
  cd backend && python reset_db.py <<< "yes" && cd ..
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start ProofGraph:"
echo "  Terminal 1:  source venv/bin/activate && cd backend && python main.py"
echo "  Terminal 2:  cd frontend && python3 -m http.server 3000"
echo "  Browser:     http://localhost:3000"
echo ""
