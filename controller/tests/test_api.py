from datetime import timedelta

from fastapi.testclient import TestClient

from app.status import utcnow
from app.store import MemoryStore


def enroll(client: TestClient, student_id: str = "jane@sheridancollege.ca") -> dict:
    res = client.post(
        "/v1/agents/enroll",
        json={"student_id": student_id, "enrollment_key": "test-enrollment-key"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_healthz(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_ui_is_served(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "Firewall AI" in res.text


def test_enroll_rejects_bad_key(client: TestClient) -> None:
    res = client.post(
        "/v1/agents/enroll",
        json={"student_id": "jane@sheridancollege.ca", "enrollment_key": "nope"},
    )
    assert res.status_code == 401


def test_heartbeat_and_offline_detection(client: TestClient, store: MemoryStore) -> None:
    creds = enroll(client)
    headers = {"Authorization": f"Bearer {creds['agent_token']}"}
    res = client.post(
        f"/v1/agents/{creds['agent_id']}/heartbeat",
        headers=headers,
        json={
            "student_id": "jane@sheridancollege.ca",
            "hostname": "PA-VM-JANE",
            "sw_version": "11.1.4",
            "mgmt_ip": "172.16.10.222",
            "serial": "015351000000001",
            "model": "PA-VM",
            "ok": True,
        },
    )
    assert res.status_code == 200

    labs = client.get("/v1/labs", headers={"Authorization": "Bearer test-admin-token"}).json()["labs"]
    assert labs[0]["online"] is True
    assert labs[0]["hostname"] == "PA-VM-JANE"
    assert labs[0]["sw_version"] == "11.1.4"

    agent = store._agents[creds["agent_id"]]
    agent.last_seen = utcnow() - timedelta(minutes=5)
    labs = client.get("/v1/labs", headers={"Authorization": "Bearer test-admin-token"}).json()["labs"]
    assert labs[0]["online"] is False


def test_heartbeat_rejects_fw_key_field(client: TestClient) -> None:
    creds = enroll(client)
    res = client.post(
        f"/v1/agents/{creds['agent_id']}/heartbeat",
        headers={"Authorization": f"Bearer {creds['agent_token']}"},
        json={"ok": True, "fw_api_key": "should-not-be-accepted"},
    )
    assert res.status_code == 422


def test_labs_requires_admin(client: TestClient) -> None:
    assert client.get("/v1/labs").status_code == 401
    assert client.get("/v1/labs", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_probe_job_roundtrip(client: TestClient) -> None:
    creds = enroll(client, "s123456")
    probe = client.post(
        "/v1/labs/s123456/probe",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert probe.status_code == 200
    job_id = probe.json()["job_id"]

    jobs = client.get(
        f"/v1/agents/{creds['agent_id']}/jobs",
        headers={"Authorization": f"Bearer {creds['agent_token']}"},
    )
    assert jobs.status_code == 200
    assert jobs.json() == [{"job_id": job_id, "type": "probe", "status": "running"}]

    done = client.post(
        f"/v1/agents/{creds['agent_id']}/jobs/{job_id}/result",
        headers={"Authorization": f"Bearer {creds['agent_token']}"},
        json={"ok": True, "hostname": "PA-VM", "sw_version": "11.1.2", "mgmt_ip": "172.16.10.10"},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "done"

    empty = client.get(
        f"/v1/agents/{creds['agent_id']}/jobs",
        headers={"Authorization": f"Bearer {creds['agent_token']}"},
    )
    assert empty.json() == []


def test_re_enroll_rotates_token(client: TestClient) -> None:
    first = enroll(client)
    second = enroll(client)
    assert first["agent_id"] == second["agent_id"]
    old = client.post(
        f"/v1/agents/{first['agent_id']}/heartbeat",
        headers={"Authorization": f"Bearer {first['agent_token']}"},
        json={"ok": True},
    )
    assert old.status_code == 401
    new = client.post(
        f"/v1/agents/{second['agent_id']}/heartbeat",
        headers={"Authorization": f"Bearer {second['agent_token']}"},
        json={"ok": True},
    )
    assert new.status_code == 200
