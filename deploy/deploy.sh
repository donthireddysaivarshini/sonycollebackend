#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Starting Sony Feeding Kurtis Production Deployment"
echo " Date: $(date -u)"
echo "=========================================================="

APP_DIR="/var/www/sonyfeedingkurtis/sony-backend"
VENV_DIR="$APP_DIR/.venv"

cd "$APP_DIR"

echo "[1/6] Pulling latest changes from GitHub repository..."
git fetch origin main
git reset --hard origin/main

echo "[2/6] Activating virtual environment & installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/6] Applying database migrations (PostgreSQL)..."
python manage.py migrate --settings=core.production_settings --no-input

echo "[4/6] Collecting static assets..."
python manage.py collectstatic --settings=core.production_settings --no-input

echo "[5/6] Restarting Gunicorn systemd service..."
sudo systemctl restart sony-backend.service
sudo systemctl status sony-backend.service --no-pager

echo "[6/6] Reloading Nginx..."
sudo nginx -t
sudo systemctl reload nginx

echo "=========================================================="
echo " Deployment Successfully Completed!"
echo " System Status: Operational at https://sonyfeedingkurtis.com"
echo "=========================================================="

