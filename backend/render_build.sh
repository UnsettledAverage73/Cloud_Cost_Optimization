#!/usr/bin/env bash
# Render Build Script for CloudPulse FinOps Backend
set -o errexit

echo "📦 Upgrading pip and installing production requirements..."
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "💾 Checking database connectivity & initializing schema..."
PYTHONPATH=backend python -c "
import os
from database.init_db import initialize_database
try:
    initialize_database()
    print('✅ Render database initialization completed successfully.')
except Exception as e:
    print(f'⚠️ Notice during build-time DB init (DB may not be reachable until runtime): {e}')
" || true

echo "✅ Backend build finished successfully!"
