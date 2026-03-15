#!/bin/bash
# ============================================================
# ProofGraph - Full Setup Script
# Run this once on your Ubuntu machine
# ============================================================

set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        ProofGraph Setup Script           ║"
echo "║   Verifiable Intelligence on OpenGradient║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ─────────────────────────────────────────────
# STEP 1: System Dependencies
# ─────────────────────────────────────────────
echo "▶ [1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  curl \
  git \
  sqlite3 \
  libsqlite3-dev \
  pkg-config

echo "✅ System dependencies installed"

# ─────────────────────────────────────────────
# STEP 2: Python Version Check
# ─────────────────────────────────────────────
echo ""
echo "▶ [2/6] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python version: $PYTHON_VERSION"

# OpenGradient requires 3.10, 3.11, or 3.12
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ] && [ "$MINOR" -le 12 ]; then
  echo "✅ Python version compatible"
else
  echo "⚠️  WARNING: OpenGradient supports Python 3.10-3.12. You have $PYTHON_VERSION"
  echo "   Consider installing Python 3.11: sudo apt install python3.11"
fi

# ─────────────────────────────────────────────
# STEP 3: Virtual Environment
# ─────────────────────────────────────────────
echo ""
echo "▶ [3/6] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
echo "✅ Virtual environment created at ./venv"

# ─────────────────────────────────────────────
# STEP 4: Python Dependencies
# ─────────────────────────────────────────────
echo ""
echo "▶ [4/6] Installing Python dependencies..."
pip install -r requirements.txt
echo "✅ Python dependencies installed"

# ─────────────────────────────────────────────
# STEP 5: OpenGradient CLI Config
# ─────────────────────────────────────────────
echo ""
echo "▶ [5/6] OpenGradient SDK installed. Run setup wizard:"
echo ""
echo "   ┌──────────────────────────────────────────────┐"
echo "   │  After this script, run:                     │"
echo "   │                                              │"
echo "   │  source venv/bin/activate                    │"
echo "   │  opengradient config init                    │"
echo "   │                                              │"
echo "   │  This sets up your wallet + gets testnet     │"
echo "   │  tokens from the faucet automatically.       │"
echo "   └──────────────────────────────────────────────┘"

# ─────────────────────────────────────────────
# STEP 6: .env Setup
# ─────────────────────────────────────────────
echo ""
echo "▶ [6/6] Setting up environment config..."
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "✅ Created backend/.env from template"
  echo ""
  echo "   ⚠️  IMPORTANT: Edit backend/.env with your credentials:"
  echo "   nano backend/.env"
else
  echo "✅ backend/.env already exists"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Setup Complete! 🎉             ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Next steps:                             ║"
echo "║                                          ║"
echo "║  1. source venv/bin/activate             ║"
echo "║  2. opengradient config init             ║"
echo "║  3. nano backend/.env  (add your keys)   ║"
echo "║  4. cd backend && python main.py         ║"
echo "║  5. Open frontend/index.html in browser  ║"
echo "╚══════════════════════════════════════════╝"
echo ""
