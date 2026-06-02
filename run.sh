#!/bin/bash

cd "$(dirname "$0")"
MYDIR=$(pwd)
echo "#########################################"
echo "✓ SWITCHING TO FOLDER OF SCRIPT-File: $MYDIR"

echo "#################################################################################"
echo "🔎 CHECKING if UV Package Manager is installed..."
if command -v uv >/dev/null 2>&1; then
  echo "✓ uv is installed"
else
  echo "⚠ uv is not installed."
  echo "Install via:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "EXITING..."
  exit 1
fi

echo "#################################################################################"
echo "🔧 SYNCING dependencies..."
uv sync 2>&1

echo "#################################################################################"
echo "🚀 RUNNING BatchSquareFill.py..."
.venv/bin/python BatchSquareFill.py

echo "#################################################################################"
echo "Press Enter to close..."
read
