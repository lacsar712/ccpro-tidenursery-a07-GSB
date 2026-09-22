# TideNursery-01 · 潮汐育苗台账

海水育苗场「塘口水质采样与投喂事件」台账种子项目（非库存 / 电商 / 医院）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic v2 · python-jose · passlib(bcrypt) · uvicorn |
| 前端 | React 18 · Vite · TypeScript · React Router v6 |
| 数据库 | PostgreSQL 15 |
| 部署 | docker-compose · 前端 Nginx 反代 `/api` |

## 端口与账号

| 服务 | 端口 |
| --- | --- |
| 前端 | **3400** |
| 后端 API | **8400** |
| PostgreSQL | **5434** |

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 场长 |
| `technician` | `123456` | 水质技术员 |

## 一键启动

```bash
cd TideNursery-01
docker compose up --build
```

启动后访问：

- 前端：http://localhost:3400
- 后端健康检查：http://localhost:8400/api/health
- API 文档：http://localhost:8400/docs

后端 entrypoint 流程：等待数据库就绪 → `create_all` 建表 → seed 初始数据 → 启动 uvicorn。

## 功能模块

1. **Auth**：JWT 登录（OAuth2 Password），`/api/auth/login`、`/api/auth/me`
2. **Hatchery 育苗场**：`name`、`seawaterSource`、`notes`
3. **Pond 育苗塘**：`hatcheryId`、`pondCode`、`species`、`volumeM3`、`status(stocked|dry|quarantine)`；同场 `pondCode` 唯一；有未解除卷宗的塘口禁止直接改回 `stocked`（返回 **409**）
4. **QuarantineCase 检疫解除卷宗**：`pondId`、`openedAt`（立案时刻）、`releasedAt`（解除时刻，可空）、`summary`（结论摘要）；仅隔离塘可立案，同塘同时只许一份未解除卷宗（重复立案返回 **409**）
5. **WaterSample 水质样**：`pondId`、`sampledAt`、`tempC`、`salinityPpt`、`doMgL`、`ph`、`notes`、`caseId`（卷宗编号）；`doMgL > 0` 且 `ph ∈ [6,9]`，否则返回 **400**；塘口有未解除卷宗时新增水样必须挂该卷宗编号，否则返回 **400**
6. **FeedEvent 投喂**：`pondId`、`fedAt`、`feedType`、`amountKg`、`operatorName`
7. **Dashboard**：塘总数、quarantine 数、近 24h 采样数、近 7 日投喂总量 kg

## 检疫解除流程

隔离塘（`status=quarantine`）要改回在养，必须凭检疫卷宗办理解除，不能直接把状态改回 `stocked`：

1. **立案**：`POST /api/quarantine-cases`，仅隔离塘可立案；同塘同时只许一份未解除卷宗。
2. **挂样监测**：立案后该塘新增水质样必须带 `caseId` 挂到卷宗（前端会自动带上），漏挂或挂错返回 **400**。
3. **解除**：`POST /api/quarantine-cases/{id}/release`，判定通过才放行——
   - 卷宗下水质样 **≥ 3 份**；
   - 且**最近一份**（按 `sampledAt`）溶解氧 `doMgL` **≥ 5 mg/L**；
   - 任一不满足返回 **409**，`releasedAt` 保持为空。
4. 解除成功：写入 `releasedAt`，塘口状态自动改为 `stocked`，可填写/更新结论摘要 `summary`。

塘口改状态接口（`PUT /api/ponds/{id}`）与解除接口共用同一套解除判定（`app/quarantine.py` 的 `evaluate_release`）：卷宗未解除时直接改 `stocked` 一律 **409**，即使条件已满足也必须走解除接口，避免"随手改回在养"。

## 前端页面

Login · Dashboard · Hatcheries · Ponds · QuarantineCases（检疫卷宗） · WaterSamples · FeedEvents

种子数据中的 A-02 塘（东港潮汐一号场）处于隔离状态，且已有一份未解除的检疫卷宗（含 1 份挂卷水质样），可直接演示"采样挂卷 → 达标解除 → 自动改回在养"全流程。

## 本地开发（可选）

```bash
# 数据库（或用 compose 只起 db）
docker compose up -d db

# 后端
cd backend
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg2://tidenursery:tidenursery@localhost:5434/tidenursery
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8400

# 前端
cd frontend
npm install
npm run dev
```

## 目录结构

```
TideNursery-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       ├── seed.py
│       ├── models/
│       ├── schemas/
│       └── routers/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── pages/
        ├── components/
        └── api/
```
