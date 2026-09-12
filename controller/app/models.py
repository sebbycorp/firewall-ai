from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

JobType = Literal["probe"]
JobStatus = Literal["pending", "running", "done", "error"]


class HeartbeatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str | None = None
    hostname: str | None = None
    sw_version: str | None = None
    mgmt_ip: str | None = None
    serial: str | None = None
    model: str | None = None
    ok: bool = True
    error: str | None = None

    @field_validator("hostname", "sw_version", "mgmt_ip", "serial", "model", "error")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class EnrollIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    enrollment_key: str | None = None


class EnrollOut(BaseModel):
    agent_id: str
    agent_token: str
    student_id: str


class JobResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str | None = None
    ok: bool = True
    error: str | None = None
    hostname: str | None = None
    sw_version: str | None = None
    mgmt_ip: str | None = None
    serial: str | None = None
    model: str | None = None


class AgentRecord(BaseModel):
    agent_id: str
    student_id: str
    token_hash: str
    hostname: str | None = None
    sw_version: str | None = None
    mgmt_ip: str | None = None
    serial: str | None = None
    model: str | None = None
    ok: bool = False
    last_error: str | None = None
    last_seen: datetime | None = None
    enrolled_at: datetime | None = None


class JobRecord(BaseModel):
    job_id: str
    agent_id: str
    student_id: str
    type: JobType = "probe"
    status: JobStatus = "pending"
    created_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class LabStatus(BaseModel):
    student_id: str
    agent_id: str
    online: bool
    last_seen: datetime | None = None
    hostname: str | None = None
    sw_version: str | None = None
    mgmt_ip: str | None = None
    serial: str | None = None
    model: str | None = None
    last_error: str | None = None
    ok: bool = False


class ProbeOut(BaseModel):
    job_id: str
    agent_id: str
    student_id: str
    type: JobType = "probe"
    status: JobStatus = "pending"


class JobOut(BaseModel):
    job_id: str
    type: JobType
    status: JobStatus


class HeartbeatOut(BaseModel):
    accepted: bool = True
    agent_id: str
    student_id: str
