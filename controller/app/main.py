from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .auth import (
    agent_id_for_student,
    bearer_token,
    hash_token,
    new_agent_token,
    normalize_student_id,
    require_admin_token,
    require_enrollment_key,
    token_matches,
)
from .config import Settings, get_settings
from .models import (
    AgentRecord,
    EnrollIn,
    EnrollOut,
    HeartbeatIn,
    HeartbeatOut,
    JobOut,
    JobResultIn,
    ProbeOut,
)
from .status import lab_status, utcnow
from .store import Store, build_store

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = store or build_store(settings.store_backend, settings.gcp_project)

    app = FastAPI(title="Firewall AI", version=__version__)
    app.state.settings = settings
    app.state.store = store
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

    def _settings() -> Settings:
        return app.state.settings

    def _store() -> Store:
        return app.state.store

    async def _admin(
        authorization: str | None = Header(default=None),
        settings: Settings = Depends(_settings),
    ) -> None:
        require_admin_token(settings.admin_token, authorization)

    async def _agent(
        agent_id: str,
        authorization: str | None = Header(default=None),
        store: Store = Depends(_store),
    ) -> AgentRecord:
        token = bearer_token(authorization)
        agent = await store.get_agent(agent_id)
        if agent is None or not token_matches(token, agent.token_hash):
            raise HTTPException(status_code=401, detail="invalid agent credentials")
        return agent

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/", response_class=HTMLResponse)
    async def instructor_ui(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"version": __version__},
        )

    @app.post("/v1/agents/enroll", response_model=EnrollOut)
    async def enroll(
        body: EnrollIn,
        authorization: str | None = Header(default=None),
        settings: Settings = Depends(_settings),
        store: Store = Depends(_store),
    ) -> EnrollOut:
        provided = body.enrollment_key
        if not provided and authorization:
            provided = bearer_token(authorization)
        require_enrollment_key(settings.enrollment_key, provided)
        student_id = normalize_student_id(body.student_id)
        agent_id = agent_id_for_student(student_id)
        raw_token = new_agent_token()
        now = utcnow()
        record = AgentRecord(
            agent_id=agent_id,
            student_id=student_id,
            token_hash=hash_token(raw_token),
            enrolled_at=now,
        )
        await store.upsert_enrollment(record)
        return EnrollOut(agent_id=agent_id, agent_token=raw_token, student_id=student_id)

    @app.post("/v1/agents/{agent_id}/heartbeat", response_model=HeartbeatOut)
    async def heartbeat(
        agent_id: str,
        body: HeartbeatIn,
        agent: AgentRecord = Depends(_agent),
        store: Store = Depends(_store),
    ) -> HeartbeatOut:
        if body.student_id:
            incoming = normalize_student_id(body.student_id)
            if incoming != agent.student_id:
                raise HTTPException(status_code=400, detail="student_id does not match agent")
        await store.apply_heartbeat(agent_id, body, utcnow())
        return HeartbeatOut(agent_id=agent.agent_id, student_id=agent.student_id)

    @app.get("/v1/agents/{agent_id}/jobs", response_model=list[JobOut])
    async def list_jobs(
        agent: AgentRecord = Depends(_agent),
        store: Store = Depends(_store),
    ) -> list[JobOut]:
        jobs = await store.claim_pending_jobs(agent.agent_id)
        return [JobOut(job_id=j.job_id, type=j.type, status=j.status) for j in jobs]

    @app.post("/v1/agents/{agent_id}/jobs/{job_id}/result")
    async def job_result(
        agent_id: str,
        job_id: str,
        body: JobResultIn,
        agent: AgentRecord = Depends(_agent),
        store: Store = Depends(_store),
    ) -> dict[str, str]:
        try:
            job = await store.complete_job(agent.agent_id, job_id, body)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        return {"job_id": job.job_id, "status": job.status}

    @app.get("/v1/labs")
    async def list_labs(
        _: None = Depends(_admin),
        settings: Settings = Depends(_settings),
        store: Store = Depends(_store),
    ) -> dict:
        now = utcnow()
        labs = [
            lab_status(agent, now=now, offline_after_sec=settings.offline_after_sec)
            for agent in await store.list_agents()
        ]
        return {
            "offline_after_sec": settings.offline_after_sec,
            "generated_at": now,
            "labs": [lab.model_dump() for lab in labs],
        }

    @app.post("/v1/labs/{student_id}/probe", response_model=ProbeOut)
    async def enqueue_probe(
        student_id: str,
        _: None = Depends(_admin),
        store: Store = Depends(_store),
    ) -> ProbeOut:
        normalized = normalize_student_id(student_id)
        agent = await store.get_agent_by_student(normalized)
        if agent is None:
            raise HTTPException(status_code=404, detail="student is not enrolled")
        job = await store.create_job(agent, job_type="probe")
        return ProbeOut(
            job_id=job.job_id,
            agent_id=agent.agent_id,
            student_id=agent.student_id,
            type=job.type,
            status=job.status,
        )

    return app


app = create_app()
