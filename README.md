# SPHWords · 宋鹏昊单词笔记

课堂原始笔记的网页版：章节浏览、辨析、自测。自测「不熟词表」支持邮箱账号，数据存 SQLite，换终端可同步。

## 本地启动（WSL）

推荐用 [uv](https://github.com/astral-sh/uv)（本机若无 `python3-venv` / `pip` 也可）：

```bash
cd ~/sphwords
# curl -LsSf https://astral.sh/uv/install.sh | sh   # 若尚未安装 uv
uv venv .venv
uv pip install -r server/requirements.txt
source .venv/bin/activate
uvicorn server.app:app --host 127.0.0.1 --port 8787 --reload
```

浏览器打开：http://127.0.0.1:8787/

- 注册：http://127.0.0.1:8787/register.html （任意合法邮箱）
- 开发模式默认不发真邮件，验证/重置链接会写在页面返回值，并追加到 `logs/auth_emails.log`
- API 文档：http://127.0.0.1:8787/api/docs

### 环境变量（可选）

| 变量 | 说明 | 默认 |
|------|------|------|
| `SPHWORDS_BASE_URL` | 邮件链接前缀 | `http://127.0.0.1:8787` |
| `SPHWORDS_USE_SMTP` | `true` 时发真邮件 | 关 |
| `SPHWORDS_DB_PATH` | SQLite 路径 | `data/sphwords.db` |

## VPS 生产

线上：http://45.119.99.168/sphwords/  
后端：`systemd` 服务 `sphwords`（uvicorn `127.0.0.1:8787`，nginx 反代 `/sphwords/`）。  
SMTP / 路径等机密在 VPS：`/etc/sphwords/sphwords.env`（不进 git）。

### GitHub Actions 自动部署

推送到 `main`（或手动 Run workflow）会：

1. 重建 `compare.html`、`drill-index.json`、`search-index.json`
2. `rsync` 到 VPS `/opt/sphwords`（保留服务器上的 `data/`、`.venv/`、`logs/`）
3. `systemctl restart sphwords`

**一次性配置 secrets**（仓库 Settings → Secrets → Actions，或用脚本）：

| Secret | 示例 |
|--------|------|
| `VPS_SSH_KEY` | 专用 deploy 私钥全文 |
| `VPS_HOST` | `45.119.99.168` |
| `VPS_USER` | `root` |
| `VPS_PATH` | `/opt/sphwords` |

本机已登录 `gh` 时：

```bash
./scripts/setup-gha-secrets.sh ~/.cursor/sphwords-gha-deploy
```

手机 Cursor 只需改章节并 push `main`，网站会自动更新。

## GitHub Pages

静态页仍可部署到 Pages，但**没有后端时**错词本只能存在浏览器。账号同步需跑本服务（VPS）。
