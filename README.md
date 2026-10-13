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

## GitHub Pages

静态页仍可部署到 Pages，但**没有后端时**错词本只能存在浏览器。账号同步需跑本服务（后续挂 VPS）。
