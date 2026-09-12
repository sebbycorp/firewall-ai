from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from urllib.parse import urlencode

SHOW_SYSTEM_INFO = "<show><system><info></info></system></show>"


@dataclass
class SystemInfo:
    ok: bool
    hostname: str | None = None
    sw_version: str | None = None
    mgmt_ip: str | None = None
    serial: str | None = None
    model: str | None = None
    error: str | None = None

    def as_heartbeat(self, student_id: str) -> dict:
        payload = asdict(self)
        payload["student_id"] = student_id
        return payload


def _text(node: ET.Element | None, tag: str) -> str | None:
    if node is None:
        return None
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def parse_system_info(xml_text: str) -> SystemInfo:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return SystemInfo(ok=False, error=f"invalid XML from firewall: {exc}")

    status = (root.attrib.get("status") or "").lower()
    if status != "success":
        msg = root.findtext(".//line") or root.findtext(".//msg") or root.findtext("result")
        return SystemInfo(ok=False, error=(msg or "firewall API error").strip())

    system = root.find(".//system")
    if system is None:
        return SystemInfo(ok=False, error="firewall response missing system info")

    return SystemInfo(
        ok=True,
        hostname=_text(system, "hostname"),
        sw_version=_text(system, "sw-version"),
        mgmt_ip=_text(system, "ip-address") or _text(system, "ipv6-address"),
        serial=_text(system, "serial"),
        model=_text(system, "model"),
    )


def api_url(fw_host: str, api_key: str, cmd: str = SHOW_SYSTEM_INFO) -> str:
    base = fw_host.rstrip("/")
    query = urlencode({"type": "op", "cmd": cmd, "key": api_key})
    return f"{base}/api/?{query}"


def mock_system_info(student_id: str) -> SystemInfo:
    return SystemInfo(
        ok=True,
        hostname="PA-VM-MOCK",
        sw_version="11.1.0",
        mgmt_ip="172.16.10.222",
        serial="MOCKSERIAL0001",
        model="PA-VM",
    )
