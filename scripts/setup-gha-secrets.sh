#!/usr/bin/env bash
# One-time: upload VPS deploy secrets to GitHub for Actions.
# Usage:
#   gh auth login
#   ./scripts/setup-gha-secrets.sh [/path/to/private_key]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${1:-$HOME/.cursor/sphwords-gha-deploy}"
HOST="${VPS_HOST:-45.119.99.168}"
USER="${VPS_USER:-root}"
PATH_ON_VPS="${VPS_PATH:-/opt/sphwords}"

if ! command -v gh >/dev/null; then
  echo "需要已安装并登录的 GitHub CLI: https://cli.github.com/"
  exit 1
fi

if [[ ! -f "$KEY" ]]; then
  echo "找不到私钥: $KEY"
  echo "请传入 deploy 私钥路径，或先生成并放到该位置。"
  exit 1
fi

cd "$ROOT"
gh secret set VPS_SSH_KEY < "$KEY"
gh secret set VPS_HOST --body "$HOST"
gh secret set VPS_USER --body "$USER"
gh secret set VPS_PATH --body "$PATH_ON_VPS"
echo "已写入仓库 secrets: VPS_SSH_KEY / VPS_HOST / VPS_USER / VPS_PATH"
echo "可在 GitHub → Actions → Deploy to VPS → Run workflow 手动试跑。"
