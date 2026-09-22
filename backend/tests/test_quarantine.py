"""检疫解除卷宗全流程测试（SQLite 文件库，随测试会话重建）。"""

import os
import uuid
from datetime import datetime, timedelta, timezone

# 必须在导入 app 之前指定测试数据库
os.environ["DATABASE_URL"] = "sqlite:////tmp/tidenursery_test.db"

if os.path.exists("/tmp/tidenursery_test.db"):
    os.remove("/tmp/tidenursery_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401  确保所有表已注册
from app.seed import seed  # noqa: E402

Base.metadata.create_all(bind=engine)
seed()

from app.main import app  # noqa: E402

client = TestClient(app)


def auth_headers() -> dict:
    res = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "123456"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


H = auth_headers()


def make_pond(status: str = "quarantine") -> dict:
    code = "T-" + uuid.uuid4().hex[:6].upper()
    res = client.post(
        "/api/ponds",
        headers=H,
        json={
            "hatcheryId": 1,
            "pondCode": code,
            "species": "中国对虾",
            "volumeM3": 50,
            "status": status,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def make_case(pond_id: int) -> dict:
    res = client.post(
        "/api/quarantine-cases",
        headers=H,
        json={"pondId": pond_id, "summary": "测试立案"},
    )
    assert res.status_code == 201, res.text
    return res.json()


def add_sample(pond_id: int, do: float, hours_ago: int, case_id=None) -> dict:
    body = {
        "pondId": pond_id,
        "sampledAt": (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(),
        "tempC": 26.0,
        "salinityPpt": 28.0,
        "doMgL": do,
        "ph": 8.0,
    }
    if case_id is not None:
        body["caseId"] = case_id
    return client.post("/api/water-samples", headers=H, json=body)


def test_seed_has_one_open_case_on_quarantine_pond():
    res = client.get("/api/quarantine-cases?openOnly=true", headers=H)
    assert res.status_code == 200
    open_cases = res.json()
    assert len(open_cases) == 1
    case = open_cases[0]
    assert case["releasedAt"] is None
    assert case["sampleCount"] == 1  # 种子水质样已挂到卷宗

    pond = client.get(f"/api/ponds/{case['pondId']}", headers=H).json()
    assert pond["pondCode"] == "A-02"
    assert pond["status"] == "quarantine"


def test_create_case_only_for_quarantine_pond():
    stocked = make_pond("stocked")
    res = client.post("/api/quarantine-cases", headers=H, json={"pondId": stocked["id"]})
    assert res.status_code == 400
    assert "仅隔离塘" in res.json()["detail"]

    dry = make_pond("dry")
    res = client.post("/api/quarantine-cases", headers=H, json={"pondId": dry["id"]})
    assert res.status_code == 400

    res = client.post("/api/quarantine-cases", headers=H, json={"pondId": 99999})
    assert res.status_code == 400


def test_one_open_case_per_pond():
    pond = make_pond("quarantine")
    make_case(pond["id"])
    res = client.post("/api/quarantine-cases", headers=H, json={"pondId": pond["id"]})
    assert res.status_code == 409


def test_sample_must_attach_open_case():
    pond = make_pond("quarantine")
    case = make_case(pond["id"])

    # 未解除卷宗的塘口：新增水质样必须挂卷宗编号
    res = add_sample(pond["id"], do=6.0, hours_ago=1)
    assert res.status_code == 400
    assert "卷宗" in res.json()["detail"]

    # 挂错卷宗编号也不行
    res = add_sample(pond["id"], do=6.0, hours_ago=1, case_id=case["id"] + 1000)
    assert res.status_code == 400

    # 挂对卷宗编号 → 201，且响应带回 caseId
    res = add_sample(pond["id"], do=6.0, hours_ago=1, case_id=case["id"])
    assert res.status_code == 201, res.text
    assert res.json()["caseId"] == case["id"]

    # 无未解除卷宗的塘口不能挂卷宗编号
    normal = make_pond("stocked")
    res = add_sample(normal["id"], do=6.0, hours_ago=1, case_id=case["id"])
    assert res.status_code == 400


def test_release_requires_three_samples_and_latest_do():
    pond = make_pond("quarantine")
    case = make_case(pond["id"])

    # 0 份水质样 → 409，解除时刻仍为空
    res = client.post(f"/api/quarantine-cases/{case['id']}/release", headers=H, json={})
    assert res.status_code == 409
    assert "不足 3 份" in res.json()["detail"]
    got = client.get(f"/api/quarantine-cases/{case['id']}", headers=H).json()
    assert got["releasedAt"] is None

    # 2 份 → 仍 409
    add_sample(pond["id"], do=6.0, hours_ago=3, case_id=case["id"])
    add_sample(pond["id"], do=6.0, hours_ago=2, case_id=case["id"])
    res = client.post(f"/api/quarantine-cases/{case['id']}/release", headers=H, json={})
    assert res.status_code == 409

    # 第 3 份但最近一份溶氧 4.2 < 5 → 409
    add_sample(pond["id"], do=4.2, hours_ago=1, case_id=case["id"])
    res = client.post(f"/api/quarantine-cases/{case['id']}/release", headers=H, json={})
    assert res.status_code == 409
    assert "溶解氧" in res.json()["detail"]
    got = client.get(f"/api/quarantine-cases/{case['id']}", headers=H).json()
    assert got["releasedAt"] is None

    # 最新一份溶氧达标 → 解除成功：写入解除时刻，塘口改回在养
    add_sample(pond["id"], do=6.5, hours_ago=0, case_id=case["id"])
    res = client.post(
        f"/api/quarantine-cases/{case['id']}/release",
        headers=H,
        json={"summary": "连续达标，准予解除"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["releasedAt"] is not None
    assert body["summary"] == "连续达标，准予解除"
    assert body["sampleCount"] == 4

    pond_after = client.get(f"/api/ponds/{pond['id']}", headers=H).json()
    assert pond_after["status"] == "stocked"

    # 重复解除 → 409
    res = client.post(f"/api/quarantine-cases/{case['id']}/release", headers=H, json={})
    assert res.status_code == 409


def test_pond_status_guard_uses_shared_evaluation():
    pond = make_pond("quarantine")
    case = make_case(pond["id"])

    # 未解除时禁止直接改回在养（即使解除条件已满足也必须走解除接口）
    res = client.put(f"/api/ponds/{pond['id']}", headers=H, json={"status": "stocked"})
    assert res.status_code == 409
    assert "禁止直接改为在养" in res.json()["detail"]

    # 其他状态变更不受限
    res = client.put(f"/api/ponds/{pond['id']}", headers=H, json={"status": "dry"})
    assert res.status_code == 200
    res = client.put(f"/api/ponds/{pond['id']}", headers=H, json={"status": "quarantine"})
    assert res.status_code == 200

    # 条件满足后直接改在养仍是 409（不是随意开关），解除接口才放行
    for i, do in enumerate([6.0, 6.1, 6.2]):
        add_sample(pond["id"], do=do, hours_ago=3 - i, case_id=case["id"])
    res = client.put(f"/api/ponds/{pond['id']}", headers=H, json={"status": "stocked"})
    assert res.status_code == 409

    res = client.post(f"/api/quarantine-cases/{case['id']}/release", headers=H, json={})
    assert res.status_code == 200
    pond_after = client.get(f"/api/ponds/{pond['id']}", headers=H).json()
    assert pond_after["status"] == "stocked"


def test_refile_after_release():
    pond = make_pond("quarantine")
    case = make_case(pond["id"])
    for i in range(3):
        add_sample(pond["id"], do=6.0 + i * 0.1, hours_ago=3 - i, case_id=case["id"])
    res = client.post(f"/api/quarantine-cases/{case['id']}/release", headers=H, json={})
    assert res.status_code == 200

    # 解除后可再次隔离并重新立案（部分唯一索引只约束未解除行）
    res = client.put(f"/api/ponds/{pond['id']}", headers=H, json={"status": "quarantine"})
    assert res.status_code == 200
    case2 = make_case(pond["id"])
    assert case2["id"] != case["id"]
    assert case2["releasedAt"] is None
