#!/usr/bin/env bash
# Instala Ollama + modelo, entorno de Python y arranca con PM2.
# La parte web (dominio, SSL, proxy) la hace HestiaCP. Ver DEPLOY.md
# Uso (desde la raíz del proyecto):  bash deploy/setup.sh
set -euo pipefail
MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"

echo "==> 1/4 Ollama"
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull "$MODEL"

echo "==> 2/4 Entorno de Python"
sudo apt-get install -y python3-venv >/dev/null
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; sed -i "s/^OLLAMA_MODEL=.*/OLLAMA_MODEL=$MODEL/" .env; }

echo "==> 3/4 PM2"
command -v pm2 >/dev/null || { echo "PM2 no está instalado (npm i -g pm2)"; exit 1; }
pm2 describe brujula-isc >/dev/null 2>&1 && pm2 restart brujula-isc || pm2 start deploy/ecosystem.config.js
pm2 save

echo "==> 4/4 Prueba local"
sleep 3
curl -s http://127.0.0.1:8010/api/health; echo
