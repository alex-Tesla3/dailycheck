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

在「分析」页可让大模型基于最近 7/30/90 天的打卡、血压、体重数据生成个性化建议。支持两种 Key 方式：

**方式一：服务器共享 Key（每人限免 5 次）**
- 在服务器配置一个共享 Key（默认 DeepSeek）：
  ```
  AI_API_KEY=sk-xxx            # 服务器共享 key
  AI_BASE_URL=https://api.deepseek.com/v1
  AI_MODEL=deepseek-chat
  AI_FREE_LIMIT=5              # 每个用户使用共享 key 的免费次数（默认 5）
  ```
- 每个用户没有自己的 Key 时，用共享 Key 最多免费分析 `AI_FREE_LIMIT` 次，用完提示去填自己的 Key。

**方式二：用户自己的 Key（推荐）**
- 登录后在「我的 → AI 设置」填写自己的 API Key / Base URL / 模型，之后分析全部走自己的 Key，无次数限制，且 Key 只存在该用户的数据库记录里，任何接口都不会返回明文 Key。

- 自托管：共享 Key 加到服务器 `.env` 后 `docker compose up -d` 生效
- Render：Settings → Environment 添加共享 Key（`AI_API_KEY` 在 `render.yaml` 已设为 `sync: false` 手动填写）
- 生成的分析会保存到 `analyses` 表，可在应用内回看/删除

> 安全提醒：API Key 是敏感信息，不要发到聊天/公开仓库；如不慎泄露请立即到对应平台重新生成。
> 提醒：AI 建议仅供参考，不替代医生诊断。

## 免费组合：Render(免费) + Supabase(免费)

这是推荐的零成本方案：**Render 免费实例会休眠（提醒暂停），但数据通过 `DATABASE_URL` 存到 Supabase，重启/重部署都不丢**。

### 一次配置步骤

1. **创建 Supabase 免费项目**：[supabase.com](https://supabase.com) → New project → 选区域（如 Singapore/ap-southeast-1）→ 记下 Database Password。
2. **复制连接串**：项目 → **Project Settings → Database → Connection string**（选 **Session pooler** 或 **Direct connection**，端口 5432）→ Copy。
   形如：`postgresql://postgres.<ref>:<密码>@aws-0-<region>.pooler.supabase.com:5432/postgres`
3. **建表**（两种方式任选，推荐 A）：
   - A（自动）：把连接串设为 `DATABASE_URL` 后启动应用，会自动建表；
   - B（手动备用）：把仓库里的 `supabase/schema.sql` 全部粘贴到 Supabase **SQL Editor** → Run。
4. **在 Render 上设置**：进入 dailycreate 服务 → **Environment** → Add Environment Variable：
   ```
   DATABASE_URL=<第 2 步复制的连接串>
   ```
   （Render 会因配置变化自动重新部署；免费实例冷启动约 30 秒）
5. 打开 `https://dailycreate.onrender.com` 正常使用，数据即写入 Supabase。

> 端口说明：连接串默认给的是 6543（transaction pooler），若应用建表报错，改用 5432 的 session pooler / direct connection，或先手动执行 `supabase/schema.sql`。

### 数据在哪里看

在 [Supabase 控制台](https://supabase.com/dashboard) → 打开你的项目：

- **Table Editor（表格）**：左侧 Table Editor，点表名即可可视化浏览/筛选数据，表包括：
  `users`（用户）、`habits`（习惯）、`checkins`（打卡记录）、`blood_pressure`（血压）、`metrics`（体重等指标）、`analyses`（AI 分析）、`invite_codes`（邀请码）、`push_subscriptions`（推送订阅）
- **SQL Editor（SQL）**：写 SQL 查询，例如：
  ```sql
  -- 最近打卡
  select h.name, c.date, c.value, c.note
  from checkins c join habits h on h.id = c.habit_id
  order by c.date desc limit 50;

  -- 血压趋势
  select measured_at, systolic, diastolic from blood_pressure order by measured_at;

  -- AI 分析历史
  select created_at, period_start, period_end, left(content, 80) from analyses order by id desc;
  ```
- 每个表都有 `user_id` 列区分家庭成员，可按 `where user_id = 1` 过滤。

### 本地开发说明

默认数据仍在本地 SQLite（`data/habits.db`）。想连 Supabase 只需在 `.env` 设 `DATABASE_URL`。`psycopg2-binary` 是唯一 Postgres 依赖；本地没有 Postgres 时会自动用 SQLite，同一套代码。免费 Supabase 有 500MB 空间，家庭用量足够。

> 注意：切换到 Supabase 后是从空库开始（本地 SQLite 的数据不会自动过去）。如需把当前本地数据导入 Supabase，可联系我加一个导入脚本。

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
