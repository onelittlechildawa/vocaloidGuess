#!/bin/bash
cd "$(dirname "$0")"
echo "Initializing database..."
python3 database.py
echo "Starting server on http://localhost:8000 ..."
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
