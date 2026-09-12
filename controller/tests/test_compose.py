from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_agent_compose_uses_host_network_and_required_env() -> None:
    data = yaml.safe_load((ROOT / "agent" / "docker-compose.yml").read_text())
    agent = data["services"]["agent"]
    assert agent["network_mode"] == "host"
    env = agent["environment"]
    for key in (
        "CONTROLLER_URL",
        "ENROLLMENT_KEY",
        "STUDENT_ID",
        "FW_HOST",
        "FW_API_KEY",
        "HEARTBEAT_INTERVAL_SEC",
        "FW_VERIFY_TLS",
    ):
        assert key in env


def test_root_compose_runs_memory_controller() -> None:
    data = yaml.safe_load((ROOT / "compose.yaml").read_text())
    env = data["services"]["controller"]["environment"]
    assert env["STORE_BACKEND"] == "memory"
    assert "8080:8080" in data["services"]["controller"]["ports"]
