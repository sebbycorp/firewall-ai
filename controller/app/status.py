from datetime import datetime, timezone

from .models import AgentRecord, LabStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_online(
    last_seen: datetime | str | None,
    now: datetime | None = None,
    offline_after_sec: int = 120,
) -> bool:
    seen = parse_iso_datetime(last_seen)
    if seen is None:
        return False
    current = now or utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (current - seen).total_seconds() < offline_after_sec


def lab_status(record: AgentRecord, now: datetime | None = None, offline_after_sec: int = 120) -> LabStatus:
    current = now or utcnow()
    online = is_online(record.last_seen, now=current, offline_after_sec=offline_after_sec)
    return LabStatus(
        student_id=record.student_id,
        agent_id=record.agent_id,
        online=online,
        last_seen=record.last_seen,
        hostname=record.hostname,
        sw_version=record.sw_version,
        mgmt_ip=record.mgmt_ip,
        serial=record.serial,
        model=record.model,
        last_error=record.last_error,
        ok=record.ok,
    )
