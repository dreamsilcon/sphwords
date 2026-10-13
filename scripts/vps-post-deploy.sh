#!/usr/bin/env bash
# Run on the VPS after rsync (restart + wait for uvicorn).
set -euo pipefail

systemctl restart sphwords
systemctl is-active --quiet sphwords
echo "service: $(systemctl is-active sphwords)"

ok=0
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/ || true)
  echo "health try ${i}: ${code}"
  if [ "${code}" = "200" ]; then
    ok=1
    break
  fi
  sleep 1
done

if [ "${ok}" != "1" ]; then
  systemctl status sphwords --no-pager || true
  journalctl -u sphwords -n 50 --no-pager || true
  exit 1
fi

echo "hub:200"
