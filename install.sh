#!/bin/bash
set -e

BASEDIR=$(dirname $0)

echo ">>> Pulling latest code..."
cd "$BASEDIR"
git pull

echo ">>> Workign with backend..."
cd "$BASEDIR/backend"

echo ""

echo ">>> Copy .env.example to .env"
cp -u .env.example .env

read -p "I created .env file. Now you need to change it. After change press y: " -n 1 -r
echo ""

if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "You have to change .env before continue."
    exit 1
fi

echo ""
read -p "Did you already running PostgreSQL and create table? Press y to continue: " -n 1 -r
echo ""

if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "You have to run PostgreSQL and create table."
    exit 1
fi

echo ">>> Install Python dependencies (if not already done)"
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo ">>> Run database migrations"
alembic upgrade head

echo ""
echo "Installation is success. Now you can deploy your app."