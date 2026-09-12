from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass

import httpx

from panos import SystemInfo, api_url, mock_system_info, parse_system_info

log = logging.getLogger("firewall-ai-agent")


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value or ""


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    controller_url: str
    student_id: str
    fw_host: str
    fw_api_key: str
    enrollment_key: str
    heartbeat_interval_sec: int
    fw_verify_tls: bool
    agent_id: str
    agent_token: str

    @classmethod
    def from_env(cls) -> "Config":
        enrollment = _env("ENROLLMENT_KEY") or _env("AGENT_TOKEN")
        return cls(
            controller_url=_env("CONTROLLER_URL", required=True).rstrip("/"),
            student_id=_env("STUDENT_ID", required=True).strip(),
            fw_host=_env("FW_HOST", required=True).strip(),
            fw_api_key=_env("FW_API_KEY"),
            enrollment_key=enrollment,
            heartbeat_interval_sec=int(_env("HEARTBEAT_INTERVAL_SEC", "30")),
            fw_verify_tls=_bool("FW_VERIFY_TLS", False),
            agent_id=_env("AGENT_ID"),
            agent_token=_env("AGENT_TOKEN") if _env("AGENT_ID") else "",
        )


def query_firewall(cfg: Config) -> SystemInfo:
    if cfg.fw_host.startswith("mock"):
        return mock_system_info(cfg.student_id)
    if not cfg.fw_api_key:
        return SystemInfo(ok=False, error="FW_API_KEY is not set")
    url = api_url(cfg.fw_host, cfg.fw_api_key)
    try:
        with httpx.Client(verify=cfg.fw_verify_tls, timeout=12.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return parse_system_info(response.text)
    except httpx.HTTPError as exc:
        return SystemInfo(ok=False, error=f"firewall unreachable: {exc}")


def enroll(cfg: Config, client: httpx.Client) -> None:
    if cfg.agent_id and cfg.agent_token:
        return
    if not cfg.enrollment_key:
        raise SystemExit("set ENROLLMENT_KEY (or AGENT_ID + AGENT_TOKEN)")
    response = client.post(
        f"{cfg.controller_url}/v1/agents/enroll",
        json={"student_id": cfg.student_id, "enrollment_key": cfg.enrollment_key},
        timeout=15.0,
    )
    response.raise_for_status()
    body = response.json()
    cfg.agent_id = body["agent_id"]
    cfg.agent_token = body["agent_token"]
    log.info("enrolled student_id=%s agent_id=%s", cfg.student_id, cfg.agent_id)


def post_heartbeat(cfg: Config, client: httpx.Client, info: SystemInfo) -> None:
    response = client.post(
        f"{cfg.controller_url}/v1/agents/{cfg.agent_id}/heartbeat",
        headers={"Authorization": f"Bearer {cfg.agent_token}"},
        json=info.as_heartbeat(cfg.student_id),
        timeout=15.0,
    )
    response.raise_for_status()


def poll_jobs(cfg: Config, client: httpx.Client) -> None:
    response = client.get(
        f"{cfg.controller_url}/v1/agents/{cfg.agent_id}/jobs",
        headers={"Authorization": f"Bearer {cfg.agent_token}"},
        timeout=15.0,
    )
    response.raise_for_status()
    for job in response.json():
        if job.get("type") != "probe":
            log.warning("skipping unsupported job type=%s", job.get("type"))
            continue
        info = query_firewall(cfg)
        client.post(
            f"{cfg.controller_url}/v1/agents/{cfg.agent_id}/jobs/{job['job_id']}/result",
            headers={"Authorization": f"Bearer {cfg.agent_token}"},
            json=info.as_heartbeat(cfg.student_id),
            timeout=15.0,
        ).raise_for_status()
        log.info("submitted probe job_id=%s ok=%s", job["job_id"], info.ok)


def loop(cfg: Config) -> None:
    with httpx.Client() as client:
        enroll(cfg, client)
        while True:
            info = query_firewall(cfg)
            try:
                post_heartbeat(cfg, client, info)
                poll_jobs(cfg, client)
                log.info(
                    "heartbeat ok=%s hostname=%s version=%s",
                    info.ok,
                    info.hostname,
                    info.sw_version,
                )
            except httpx.HTTPError as exc:
                log.error("controller error: %s", exc)
            time.sleep(max(5, cfg.heartbeat_interval_sec))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    # Never dump env — it can contain FW_API_KEY / tokens.
    cfg = Config.from_env()
    log.info("starting agent student_id=%s controller=%s", cfg.student_id, cfg.controller_url)
    loop(cfg)


if __name__ == "__main__":
    main()
