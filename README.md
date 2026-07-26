# 信笺 · Outlook 邮箱工作台

FastAPI + Svelte 前后端分离。管理上千 Outlook 账号、`+tag` 别名、IMAP 读信与验证码提取。UI 为日式极简（wabi-sabi）。

## 结构

```
backend/app/
  routers/          auth / accounts / mail / settings
  services/         mail.py(OAuth+IMAP) / probe_job.py / scheduler.py
  db.py             原生 sqlite3 + WAL
frontend/src/
  lib/ui/           Modal / Pager / Field / ConfirmDialog / Toast …
  lib/mail/         MailBody / mailHtml / CodeChips
  lib/stores/       toast / keymap
  pages/admin/      Admin 外壳 + 侧栏 + 邮件面板 + modals/
  pages/User.svelte 公开查询页
data/               SQLite（运行时）
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | 会话签名密钥（必填） |
| `ADMIN_PASSWORD` | 管理端密码（必填） |
| `DB_PATH` | SQLite 路径；Docker 内为 `/app/data/mail.db` |
| `CORS_ORIGINS` | 跨域源；同域部署可留空 |
| `COOKIE_SECURE` | HTTPS 时设 `true` |
| `HOST_PORT` | 宿主机端口，默认 `8080`（仅 compose） |

复制 `.env.example` 为 `.env` 并填写。

## 本地开发

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY=dev-secret ADMIN_PASSWORD=dev-pass
export PYTHONPATH=.
uvicorn app.main:app --reload --port 8080

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

- 公开页：http://localhost:5173/
- 管理端：http://localhost:5173/admin

## Docker 部署（推荐生产）

镜像为单容器：构建前端静态资源 + FastAPI，同端口提供页面与 `/api`。SQLite 挂载到宿主机 `./data`。

### 1. 准备服务器

- Docker + Docker Compose 插件
- 开放端口（默认 `8080`，或反代 80/443）

### 2. 上传代码并配置

```bash
# 在服务器项目目录
cp .env.example .env
# 编辑 .env：务必改掉 SECRET_KEY、ADMIN_PASSWORD
# 生成密钥示例：
#   openssl rand -hex 32
```

生产 `.env` 最小示例：

```env
SECRET_KEY=<openssl-rand-hex-32>
ADMIN_PASSWORD=<强密码>
CORS_ORIGINS=
COOKIE_SECURE=false
HOST_PORT=8080
```

若前面有 **HTTPS 反代**（Nginx / Caddy），设 `COOKIE_SECURE=true`，并反代到 `127.0.0.1:8080`。

### 3. 构建并启动

```bash
mkdir -p data
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

- 站点：`http://<服务器IP>:8080/`
- 管理端：`http://<服务器IP>:8080/admin`
- 健康检查：`http://<服务器IP>:8080/api/health`

### 4. 常用运维

```bash
docker compose pull   # 若使用预构建镜像时
docker compose up -d --build   # 代码更新后重建
docker compose restart
docker compose down            # 停止（保留 ./data）
```

数据备份：拷贝宿主机 `./data/mail.db`（及可选的 `-wal`/`-shm`；停服后拷贝最稳妥）。

### 5. 可选 Nginx 反代

```nginx
server {
    listen 80;
    server_name mail.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

HTTPS 配好后将 `COOKIE_SECURE=true` 并 `docker compose up -d`。

> **注意**：容器内为单进程 uvicorn。内置邮箱探测调度器依赖单实例，请勿加多 worker / 多副本。

## 凭据格式

```
邮箱----密码----client_id----refresh_token
```

`client_id` / `refresh_token` 顺序可自动识别（UUID 为 client_id）。

## 后台探测

管理端 **配置** 可开关定时批量探测（默认开启，间隔 **10 分钟**）：

| 项 | 默认 | 说明 |
|----|------|------|
| 启用 | 开 | 进程内守护线程 |
| 间隔 | 10 分钟 | 每轮之间等待 |
| 每批数量 | 40 | 单轮最多探测账号数 |
| 并发 | 6 | 线程池 |
| 陈旧阈值 | 24 小时 | 优先未测 / 异常 / 最久未检 |

配置存在 SQLite `settings` 表，无需改环境变量。

## 管理端操作

| 能力 | 说明 |
|----|----|
| 多选批量 | 勾选账号后底部浮出操作条：批量探测 / 批量删除 / 导出凭据 |
| 邮件搜索 | 按主题 / 发件人 / 全文，映射到 IMAP `SUBJECT`/`FROM`/`TEXT` |
| 快捷键 | `/` 聚焦搜索、`j`/`k` 上下切账号、`r` 刷新、`Esc` 返回；输入框内不触发 |
| 自动刷新 | 30 秒一次，标签页切到后台时暂停，回到前台立即补一次 |
| 操作日志 | 支持分页与按 action 类型筛选 |
| 附件 | 详情页列出文件名与大小，点击下载。**仅管理端可用** —— 公开页的 token 走请求头传递，无法用于浏览器下载导航 |

**`codes_only`（仅显示验证码）**：验证码只能从正文判断，服务端无法预先算出总页数，
因此该模式改用「上一页 / 下一页 + `has_more`」而非页码，且单次扫描封顶 600 封。

## 安全

- 管理接口需 Cookie 会话
- 公开读信需 `/api/lookup` 签发的短期 token（`X-Public-Token`）。
  token 内绑定 `filter_to`，`search` 参数只能在其之上收窄，无法绕过别名边界
- 邮件正文经 `lettersanitizer` 清洗后放进 iframe 渲染，
  sandbox 不含 `allow-scripts` 与 `allow-same-origin`
- 勿将 `.env`、真实 token 提交仓库

> **导出凭据的代价**：`GET /api/accounts/export` 会把明文密码与 `refresh_token`
> 写成 CSV 下载到本地。接口强制 `confirm=1`、强制记入 `ops_log`、响应 `no-store`，
> 但文件一旦落盘就等同于交出这些账号的完整控制权。
>
> 同理，`data/mail.db` 中凭据为明文存储，备份该文件等于备份全部凭据。
