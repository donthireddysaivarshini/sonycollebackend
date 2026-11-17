#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# Sony Feeding Kurtis - Ubuntu 24.04 LTS VPS Provisioning Script
# Installs PostgreSQL 16, Python 3.12, Nginx, Certbot, UFW
# ==========================================================

echo "[1/7] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    curl \
    git \
    ufw \
    nginx \
    certbot \
    python3-certbot-nginx \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    build-essential \
    libpq-dev \
    postgresql \
    postgresql-contrib

echo "[2/7] Configuring UFW Firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status verbose

echo "[3/7] Setting up PostgreSQL 16..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo -u postgres psql -c "CREATE USER sony_user WITH PASSWORD 'change_this_strong_password_in_production';" || true
sudo -u postgres psql -c "CREATE DATABASE sony_db OWNER sony_user;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sony_db TO sony_user;" || true

echo "[4/7] Creating application directories..."
sudo mkdir -p /var/www/sonyfeedingkurtis/sony-backend
sudo mkdir -p /var/www/sonyfeedingkurtis/frontend/dist
sudo mkdir -p /var/log/gunicorn
sudo mkdir -p /var/www/certbot

sudo chown -R www-data:www-data /var/www/sonyfeedingkurtis
sudo chown -R www-data:www-data /var/log/gunicorn

echo "[5/7] Linking Systemd & Nginx configs..."
# cp deploy/gunicorn.service /etc/systemd/system/sony-backend.service
# cp deploy/nginx.conf /etc/nginx/sites-available/sonyfeedingkurtis
# ln -s /etc/nginx/sites-available/sonyfeedingkurtis /etc/nginx/sites-enabled/

echo "[6/7] Obtaining SSL Certificates..."
echo "Run once DNS records point to VPS IP:"
echo "sudo certbot --nginx -d sonyfeedingkurtis.com -d www.sonyfeedingkurtis.com -d api.sonyfeedingkurtis.com"

echo "[7/7] Provisioning complete!"
