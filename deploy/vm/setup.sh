#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu VM (Oracle Cloud Always Free, ARM or x86).
# Run from the repo root:  bash deploy/vm/setup.sh
set -euo pipefail

cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null; then
  echo "==> installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. Log out and back in (for the docker group), then re-run this script."
  exit 0
fi

# Oracle's Ubuntu images ship iptables rules that drop everything except SSH,
# even when the cloud security list allows 80/443. Open them on the host too.
if sudo iptables -L INPUT -n | grep -q "REJECT"; then
  echo "==> opening ports 80 and 443 in the host firewall"
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
  sudo apt-get install -y -qq iptables-persistent >/dev/null || true
  sudo netfilter-persistent save || true
fi

if [ ! -f deploy/vm/.env ]; then
  cp deploy/vm/.env.example deploy/vm/.env
  sed -i "s/^SECRET_KEY=$/SECRET_KEY=$(openssl rand -hex 32)/" deploy/vm/.env
  echo "Created deploy/vm/.env with a fresh SECRET_KEY. Fill in the rest, then re-run."
  exit 0
fi

echo "==> building sandbox images (first run takes a while; C++ is ~2 GB)"
./sandbox/build.sh

echo "==> starting the stack"
cd deploy/vm
docker compose up -d --build
docker compose ps
echo
echo "Check: curl https://\$(grep ^DOMAIN= .env | cut -d= -f2)/health"
