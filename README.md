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
3. **Pond 育苗塘**：`hatcheryId`、`pondCode`、`species`、`volumeM3`、`status(stocked|dry|quarantine)`；同场 `pondCode` 唯一
4. **QuarantineDossier 检疫卷宗**：`pondId`、`openedAt`、`releasedAt(可空)`、`conclusion`；解除隔离的正式流程，详见下文
5. **WaterSample 水质样**：`pondId`、`dossierId(可空)`、`sampledAt`、`tempC`、`salinityPpt`、`doMgL`、`ph`、`notes`；`doMgL > 0` 且 `ph ∈ [6,9]`，否则返回 **400**
6. **FeedEvent 投喂**：`pondId`、`fedAt`、`feedType`、`amountKg`、`operatorName`
7. **Dashboard**：塘总数、quarantine 数、近 24h 采样数、近 7 日投喂总量 kg

## 检疫解除卷宗（QuarantineDossier）

隔离塘（`quarantine`）改回在养（`stocked`）必须走卷宗解除流程，**不是随意改状态的开关**。

**立案** `POST /api/quarantine-dossiers`

- 仅隔离塘可立案，否则 **400**
- 同塘同时只许一份未解除卷宗（数据库部分唯一索引兜底），重复立案 **409**
- 字段：所属塘口 `pondId`、立案时刻 `openedAt`、解除时刻 `releasedAt`（可空）、结论摘要 `conclusion`

**水质样强制挂卷宗**

- 塘口存在未解除卷宗时，新增水质样必须带该卷宗的 `dossierId`，缺失或不一致返回 **400**

**解除** `POST /api/quarantine-dossiers/{id}/release`

- 解除条件（缺一不可，否则 **409** 且 `releasedAt` 保持为空）：
  1. 卷宗下水质样 **≥ 3 份**
  2. 最近一份（按 `sampledAt`）水质样溶氧 **doMgL ≥ 5 mg/L**
- 解除成功：写入 `releasedAt`，并把塘口状态改为 `stocked`

**状态守卫**

- 塘口有未解除卷宗时，`PUT /api/ponds/{id}` 直接把状态改成 `stocked` 返回 **409**
- 改状态接口与解除判定共用 `backend/app/quarantine.py` 中的 `apply_pond_status` / `evaluate_release`

**种子数据**：东港潮汐一号场 `A-02`（日本对虾）为隔离塘，已立案且卷宗未解除（含 1 份挂卷水质样），可用来演示「采样 → 满足条件 → 解除」全流程。

## 前端页面

Login · Dashboard · Hatcheries · Ponds · QuarantineDossiers（检疫卷宗） · WaterSamples · FeedEvents

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
