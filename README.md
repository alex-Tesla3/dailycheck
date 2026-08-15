# 每日打卡（家庭自托管 · 手机端优先）

记录每日锻炼、吃药等习惯，支持打卡、日历统计、连续天数、月度达成率、**血压记录与趋势图**，并通过浏览器推送（Web Push）在设定时间提醒未完成的习惯。家庭成员凭邀请码各自注册账号。

## 功能一览

- **今日打卡**：逐日打卡，可填写数值（如锻炼 30 分钟、吃药 1 粒）与备注，支持补打卡（点击日历过去的日期）
- **日历与统计**：月度日历着色（全完成/部分/未完成）、每个习惯的连续天数与月度达成率
- **血压记录**：录入收缩压/舒张压/脉搏/备注，最近 30/90/180 天趋势图（含 140/90 参考线）与平均值，记录按正常/正常高值/偏高着色
- **体重/指标记录**：记录体重、体脂率、血糖等任意数值指标（名称+数值+单位），随时查看最新值
- **AI 健康分析**：基于近 7/30/90 天的打卡、血压、体重数据，调用大模型生成个性化趋势评价与改进建议（OpenAI 兼容接口，可对接 OpenAI/DeepSeek 等），历史分析可回看
- **Supabase / Postgres 支持**：数据可存到 Supabase 的 Postgres 数据库，之后可在 Supabase 控制台直接查询历史记录、分析详情、统计结果
- **提醒通知**：每个习惯可设提醒时间，到点且当天未完成时向手机推送；需要 HTTPS + 浏览器通知授权
- **多人共用**：管理员生成一次性邀请码，成员凭邀请码注册；管理员可停用成员
- **PWA**：手机浏览器"添加到主屏幕"后像 App 一样使用

## 技术栈

- 后端：Python + FastAPI；数据库支持 **SQLite（默认）与 PostgreSQL / Supabase**（通过 `DATABASE_URL` 自动切换）
- 定时提醒：内置线程调度，每分钟检查一次
- 推送：自研 Web Push（RFC 8291/8188，VAPID 密钥首次启动自动生成），使用 `cryptography` + `requests`
- 前端：原生 HTML/CSS/JS 单页应用（无构建步骤），PWA Service Worker
- 部署：Docker Compose（app + Caddy 自动 HTTPS）

## 本地开发运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
DATA_DIR=./data .venv/bin/uvicorn app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000 ，第一个注册的账号自动成为管理员。

## 服务器快速部署（一条命令）

仓库已附 `deploy.sh`，在服务器上三步完成：

```bash
# 方式 A：本机打包后上传（本机执行）
./tools/package.sh                          # 生成 dailycreate-deploy.tar.gz
scp dailycreate-deploy.tar.gz root@服务器IP:/opt/
# 服务器上执行
cd /opt && tar -xzf dailycreate-deploy.tar.gz && cd dailycreate*
./deploy.sh                                 # 按提示输入你的域名，其余自动完成
```

```bash
# 方式 B：服务器直接 clone 仓库
git clone <你的仓库地址> && cd <目录> && ./deploy.sh
```

`deploy.sh` 会：检查 Docker → 生成 `.env`（域名 + 随机 SESSION_SECRET）→ `docker compose up -d --build` → 提示访问地址。**前提**：服务器已安装 Docker、80/443 端口放行、域名 DNS 已解析到服务器公网 IP。

## Docker 部署

1. 把域名 DNS 解析到服务器 IP。
2. 准备 `.env` 文件（参考 `.env.example`）：

   ```
   DOMAIN=checkin.example.com
   SESSION_SECRET=用 openssl rand -hex 32 生成
   VAPID_SUBJECT=mailto:admin@example.com
   ```

3. 启动：

   ```bash
   docker compose up -d --build
   ```

4. 访问 `https://你的域名`，注册第一个账号（管理员），在「我的 → 管理后台」生成邀请码发给家人。

数据保存在 Docker 卷 `habits_data`（SQLite 文件 `/data/habits.db`），升级用 `docker compose up -d --build`。

## Render 部署（可选）

Render 是云平台（PaaS），优点：自带 HTTPS、不用自己买服务器和管理证书。仓库自带 `render.yaml`，**当前为免费套餐版**：可先免费体验界面功能，但免费实例会休眠（定时提醒暂停）、无持久磁盘（SQLite 数据在重新部署时丢失）、750 免费小时/月由工作区所有免费服务共享。**正式使用请升级 Starter（约 $7/月）+ 1GB 持久磁盘**（把 `render.yaml` 的 `plan` 改回 `starter` 并启用注释中的 `disk` 块）。

步骤：

1. 把项目推送到 GitHub 仓库。
2. 在 Render 控制台选 **New → Blueprint**，连接该仓库。
3. Render 会自动识别 `render.yaml` 构建并部署；首次部署时按提示填写 `SESSION_SECRET`（用 `openssl rand -hex 32` 生成）。
4. 部署完成后访问 `https://<应用名>.onrender.com`，注册第一个账号（管理员）→ 在「我的 → 管理后台」生成邀请码。
5. 如需自定义域名：Settings → Custom Domain 绑定你的域名（Render 自动续证书）。

> 说明：Render 部署时**不需要** `docker-compose.yml` 和 `Caddyfile`（Render 自己处理 HTTPS 反向代理）；数据保存在挂载的持久磁盘 `/data`。

## 自托管（自己的服务器）对比

- 自己服务器 + Docker Compose + Caddy：数据完全自己掌控，约等于一台小服务器费用；需要域名解析到服务器。步骤见上文「Docker 部署」。
- 两者都支持手机推送通知（都满足 HTTPS）。

## AI 健康分析（可选）

在「分析」页可让大模型基于最近 7/30/90 天的打卡、血压、体重数据生成个性化建议。需配置环境变量（OpenAI 兼容接口，可对接 OpenAI / DeepSeek / Moonshot / 智谱等）：

```
AI_API_KEY=sk-xxx            # 必填（不填则分析页会提示未配置）
AI_BASE_URL=https://api.openai.com/v1   # 用 DeepSeek 等可改
AI_MODEL=gpt-4o-mini
```

- 自托管：加到服务器 `.env` 后 `docker compose up -d` 生效
- Render：Settings → Environment 添加上述变量，或直接在 `render.yaml` 的 `envVars` 里填写（`AI_API_KEY` 已设为 `sync: false` 手动填写）
- 生成的分析会保存到 `analyses` 表，可在应用内回看/删除

> 提醒：AI 建议仅供参考，不替代医生诊断。

## Supabase / PostgreSQL 数据库（可选）

默认数据存在本地 SQLite（`data/habits.db`）。想用 Supabase 存数据、并以后直接在 Supabase 控制台查询历史记录/分析详情/统计结果：

1. 在 [supabase.com](https://supabase.com) 创建免费项目（选个离你近的区域）。
2. 打开项目 → **Project Settings → Database → Connection string**（或 **Pooler**），复制 `postgresql://...` 连接串。
3. 把连接串设为环境变量 `DATABASE_URL`（自托管 `.env`，或 Render 的 Environment）：
   ```
   DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
4. 重启应用后会自动建表（users/habits/checkins/blood_pressure/metrics/analyses 等）。
5. 之后在 Supabase 控制台 **SQL Editor** 直接查数据，例如：
   ```sql
   select * from checkins order by date desc limit 20;
   select * from analyses order by created_at desc;
   ```

> 说明：`psycopg2-binary` 是唯一的 Postgres 依赖；本地开发若无 Postgres 会自动回退 SQLite，两种数据库同一套代码。免费 Supabase 有 500MB 数据库空间，家庭用量足够。

## 手机与推送通知

- 手机浏览器（Chrome/Safari 均可）打开域名后，在「我的 → 提醒通知」点击"开启推送"并允许通知
- Android Chrome / iOS Safari 支持"添加到主屏幕"，之后可从桌面图标直接打开
- 推送必须 HTTPS（Caddy 已自动签发证书）；桌面/手机通知权限需在浏览器设置里允许

## 提醒规则

- 后台每分钟检查一次；某习惯设了提醒时间、到点且**当天还没打卡**时才推送，一天最多一次
- 服务器需保持运行（Docker `restart: unless-stopped` 已配置）

## 备份

数据就是 SQLite 文件，停服后直接复制，或用 sqlite 在线备份：

```bash
# 在容器内执行
docker compose exec app sqlite3 /data/habits.db ".backup /backup/habits-$(date +%F).db"
```

建议配合服务器定时任务每日备份到其他磁盘。

## 测试

无需 pytest 也可运行（内置极简运行器）：

```bash
python3 tests/run_tests.py
```

装有 pytest 的环境也可直接 `pytest tests/test_app.py`。覆盖：认证/邀请码、习惯权限隔离、打卡与补打卡、月度统计与连续天数、血压增删改与校验、推送订阅、管理后台停用成员、Web Push 加密正确性。
