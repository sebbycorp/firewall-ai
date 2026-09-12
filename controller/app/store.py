from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from .models import AgentRecord, HeartbeatIn, JobRecord, JobResultIn
from .status import utcnow


class Store(Protocol):
    async def upsert_enrollment(self, agent: AgentRecord) -> AgentRecord: ...
    async def get_agent(self, agent_id: str) -> AgentRecord | None: ...
    async def get_agent_by_student(self, student_id: str) -> AgentRecord | None: ...
    async def list_agents(self) -> list[AgentRecord]: ...
    async def apply_heartbeat(self, agent_id: str, payload: HeartbeatIn, seen_at: datetime) -> AgentRecord: ...
    async def create_job(self, agent: AgentRecord, job_type: str = "probe") -> JobRecord: ...
    async def claim_pending_jobs(self, agent_id: str) -> list[JobRecord]: ...
    async def complete_job(self, agent_id: str, job_id: str, result: JobResultIn) -> JobRecord: ...


class MemoryStore:
    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}
        self._jobs: dict[str, dict[str, JobRecord]] = {}
        self._lock = asyncio.Lock()

    async def upsert_enrollment(self, agent: AgentRecord) -> AgentRecord:
        async with self._lock:
            existing = self._agents.get(agent.agent_id)
            if existing:
                existing.token_hash = agent.token_hash
                existing.student_id = agent.student_id
                self._agents[agent.agent_id] = existing
                return existing
            self._agents[agent.agent_id] = agent
            self._jobs.setdefault(agent.agent_id, {})
            return agent

    async def get_agent(self, agent_id: str) -> AgentRecord | None:
        async with self._lock:
            return self._agents.get(agent_id)

    async def get_agent_by_student(self, student_id: str) -> AgentRecord | None:
        async with self._lock:
            for agent in self._agents.values():
                if agent.student_id == student_id:
                    return agent
            return None

    async def list_agents(self) -> list[AgentRecord]:
        async with self._lock:
            return sorted(self._agents.values(), key=lambda a: a.student_id)

    async def apply_heartbeat(self, agent_id: str, payload: HeartbeatIn, seen_at: datetime) -> AgentRecord:
        async with self._lock:
            agent = self._agents[agent_id]
            agent.hostname = payload.hostname
            agent.sw_version = payload.sw_version
            agent.mgmt_ip = payload.mgmt_ip
            agent.serial = payload.serial
            agent.model = payload.model
            agent.ok = payload.ok
            agent.last_error = payload.error
            agent.last_seen = seen_at
            return agent

    async def create_job(self, agent: AgentRecord, job_type: str = "probe") -> JobRecord:
        async with self._lock:
            job = JobRecord(
                job_id=str(uuid4()),
                agent_id=agent.agent_id,
                student_id=agent.student_id,
                type=job_type,  # type: ignore[arg-type]
                status="pending",
                created_at=utcnow(),
            )
            self._jobs.setdefault(agent.agent_id, {})[job.job_id] = job
            return job

    async def claim_pending_jobs(self, agent_id: str) -> list[JobRecord]:
        async with self._lock:
            claimed: list[JobRecord] = []
            for job in self._jobs.get(agent_id, {}).values():
                if job.status == "pending":
                    job.status = "running"
                    claimed.append(job)
            return claimed

    async def complete_job(self, agent_id: str, job_id: str, result: JobResultIn) -> JobRecord:
        async with self._lock:
            jobs = self._jobs.get(agent_id, {})
            job = jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job.status = "done" if result.ok else "error"
            job.completed_at = utcnow()
            job.error = result.error
            job.result = result.model_dump(exclude_none=True)
            agent = self._agents.get(agent_id)
            if agent is not None:
                agent.hostname = result.hostname or agent.hostname
                agent.sw_version = result.sw_version or agent.sw_version
                agent.mgmt_ip = result.mgmt_ip or agent.mgmt_ip
                agent.serial = result.serial or agent.serial
                agent.model = result.model or agent.model
                agent.ok = result.ok
                agent.last_error = result.error
                agent.last_seen = utcnow()
            return job


class FirestoreStore:
    def __init__(self, project: str | None = None) -> None:
        from google.cloud import firestore

        self._db = firestore.AsyncClient(project=project)

    def _agent_ref(self, agent_id: str):
        return self._db.collection("agents").document(agent_id)

    def _jobs(self, agent_id: str):
        return self._agent_ref(agent_id).collection("jobs")

    @staticmethod
    def _agent_from_doc(agent_id: str, data: dict) -> AgentRecord:
        return AgentRecord(agent_id=agent_id, **data)

    async def upsert_enrollment(self, agent: AgentRecord) -> AgentRecord:
        ref = self._agent_ref(agent.agent_id)
        snap = await ref.get()
        if snap.exists:
            await ref.update(
                {
                    "token_hash": agent.token_hash,
                    "student_id": agent.student_id,
                }
            )
            data = (await ref.get()).to_dict() or {}
            return self._agent_from_doc(agent.agent_id, data)
        await ref.set(agent.model_dump())
        return agent

    async def get_agent(self, agent_id: str) -> AgentRecord | None:
        snap = await self._agent_ref(agent_id).get()
        if not snap.exists:
            return None
        return self._agent_from_doc(agent_id, snap.to_dict() or {})

    async def get_agent_by_student(self, student_id: str) -> AgentRecord | None:
        query = self._db.collection("agents").where("student_id", "==", student_id).limit(1)
        async for snap in query.stream():
            return self._agent_from_doc(snap.id, snap.to_dict() or {})
        return None

    async def list_agents(self) -> list[AgentRecord]:
        agents: list[AgentRecord] = []
        async for snap in self._db.collection("agents").stream():
            agents.append(self._agent_from_doc(snap.id, snap.to_dict() or {}))
        agents.sort(key=lambda a: a.student_id)
        return agents

    async def apply_heartbeat(self, agent_id: str, payload: HeartbeatIn, seen_at: datetime) -> AgentRecord:
        ref = self._agent_ref(agent_id)
        await ref.update(
            {
                "hostname": payload.hostname,
                "sw_version": payload.sw_version,
                "mgmt_ip": payload.mgmt_ip,
                "serial": payload.serial,
                "model": payload.model,
                "ok": payload.ok,
                "last_error": payload.error,
                "last_seen": seen_at,
            }
        )
        snap = await ref.get()
        return self._agent_from_doc(agent_id, snap.to_dict() or {})

    async def create_job(self, agent: AgentRecord, job_type: str = "probe") -> JobRecord:
        job = JobRecord(
            job_id=str(uuid4()),
            agent_id=agent.agent_id,
            student_id=agent.student_id,
            type=job_type,  # type: ignore[arg-type]
            status="pending",
            created_at=utcnow(),
        )
        await self._jobs(agent.agent_id).document(job.job_id).set(job.model_dump())
        return job

    async def claim_pending_jobs(self, agent_id: str) -> list[JobRecord]:
        claimed: list[JobRecord] = []
        query = self._jobs(agent_id).where("status", "==", "pending")
        async for snap in query.stream():
            await snap.reference.update({"status": "running"})
            data = snap.to_dict() or {}
            data["status"] = "running"
            claimed.append(JobRecord(job_id=snap.id, **{k: v for k, v in data.items() if k != "job_id"}))
        return claimed

    async def complete_job(self, agent_id: str, job_id: str, result: JobResultIn) -> JobRecord:
        job_ref = self._jobs(agent_id).document(job_id)
        snap = await job_ref.get()
        if not snap.exists:
            raise KeyError(job_id)
        now = utcnow()
        status = "done" if result.ok else "error"
        payload = {
            "status": status,
            "completed_at": now,
            "error": result.error,
            "result": result.model_dump(exclude_none=True),
        }
        await job_ref.update(payload)
        agent_update = {
            "ok": result.ok,
            "last_error": result.error,
            "last_seen": now,
        }
        if result.hostname:
            agent_update["hostname"] = result.hostname
        if result.sw_version:
            agent_update["sw_version"] = result.sw_version
        if result.mgmt_ip:
            agent_update["mgmt_ip"] = result.mgmt_ip
        if result.serial:
            agent_update["serial"] = result.serial
        if result.model:
            agent_update["model"] = result.model
        await self._agent_ref(agent_id).update(agent_update)
        data = (await job_ref.get()).to_dict() or {}
        return JobRecord(job_id=job_id, **{k: v for k, v in data.items() if k != "job_id"})


def build_store(backend: str, project: str) -> Store:
    if backend == "firestore":
        return FirestoreStore(project=project)
    return MemoryStore()
