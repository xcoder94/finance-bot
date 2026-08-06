#!/bin/bash
set -e

BASEDIR=$(pwd)
BACKEND_NODE_PORT=5001
BACKEND_NODE_NAME="financebot-backend"

echo ">>> Pulling latest code..."
cd "$BASEDIR"
git checkout -- frontend/package-lock.json 2>/dev/null || true
git pull

echo ">>> Updating backend..."
cd "$BASEDIR/backend"
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
deactivate

echo ">>> Running the API"

pm2 stop $BACKEND_NODE_NAME 2>/dev/null || true
pm2 delete $BACKEND_NODE_NAME 2>/dev/null || true

pm2 start ./venv/bin/gunicorn \
  --name financebot-backend \
  --interpreter none \
  -- \
  app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 127.0.0.1:5001 \
  --access-logfile - \
  --error-logfile -

echo ">>> Running frontend"
echo $BASEDIR
echo ""
cd "$BASEDIR/frontend"
npm i --legacy-peer-deps

pm2 delete financebot-frontend 2>/dev/null || true

pm2 start npm \
  --name financebot-frontend \
  -- run dev

echo ">>> Deploy finished."