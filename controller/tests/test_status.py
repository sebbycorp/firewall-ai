from datetime import datetime, timedelta, timezone

from app.models import AgentRecord
from app.status import is_online, lab_status, parse_iso_datetime


def test_missing_last_seen_is_offline() -> None:
    assert is_online(None) is False
    assert is_online("") is False


def test_recent_heartbeat_is_online() -> None:
    now = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)
    seen = now - timedelta(seconds=30)
    assert is_online(seen, now=now, offline_after_sec=120) is True


def test_stale_heartbeat_is_offline() -> None:
    now = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)
    seen = now - timedelta(seconds=121)
    assert is_online(seen, now=now, offline_after_sec=120) is False


def test_boundary_is_offline() -> None:
    now = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)
    seen = now - timedelta(seconds=120)
    assert is_online(seen, now=now, offline_after_sec=120) is False


def test_parses_zulu_and_naive_iso() -> None:
    parsed = parse_iso_datetime("2026-09-12T18:00:00Z")
    assert parsed is not None
    assert parsed.tzinfo is not None
    naive = parse_iso_datetime("2026-09-12T18:00:00")
    assert naive.tzinfo is not None


def test_lab_status_uses_threshold() -> None:
    now = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)
    record = AgentRecord(
        agent_id="a1",
        student_id="s1@sheridancollege.ca",
        token_hash="abc",
        last_seen=now - timedelta(minutes=3),
        ok=True,
    )
    status = lab_status(record, now=now, offline_after_sec=120)
    assert status.online is False
    record.last_seen = now - timedelta(seconds=10)
    assert lab_status(record, now=now, offline_after_sec=120).online is True
