# Firewall AI — design (MVP)

Central lab controller so Sheridan instructors can see whether each student’s Palo Alto PA-VM is up, without storing firewall credentials or tunneling into student homes.

## Goals

- Students run a small Docker agent on the **management** LAN beside their PA-VM
- The agent calls home over HTTPS to a Cloud Run controller in GCP project `firewall-ai`
- Instructors see online/offline plus last-seen metadata
- Instructors can enqueue an on-demand `probe` job; the agent runs it locally

## Non-goals (do not build)

VPN, NetBird, multi-vendor devices, grading, storing FW API keys in Firestore/Secret Manager, SLATE integration.

## Architecture

```
Student mgmt LAN                         GCP project: firewall-ai (Toronto)
┌──────────────────────────┐             ┌─────────────────────────────────┐
│  PA-VM  <── XML API ──►  │  HTTPS      │  Cloud Run  ──► Firestore       │
│           Agent (Docker) ├────────────►│  FastAPI    ──► Secret Manager  │
└──────────────────────────┘  outbound   │       ▲                         │
                                         │       │ Bearer ADMIN_TOKEN      │
                                         │  Instructor browser             │
                                         └─────────────────────────────────┘
```

The controller never initiates a connection to a student network. All control-plane traffic is **agent pull** (heartbeat + job poll) plus an instructor-facing HTTPS UI.

## Region

**`northamerica-northeast2` (Toronto)** for Cloud Run and Firestore Native.

Firestore Native is available in Toronto (no App Engine in that region; this app does not use App Engine). Fallback if a quota or org policy blocks NE2: `us-central1` — change `REGION` in `infra/deploy.sh`.

## Components

| Piece | Runtime | Notes |
| --- | --- | --- |
| Controller | Python FastAPI on Cloud Run | Serves `/`, `/healthz`, `/v1/*` |
| Datastore | Firestore Native `(default)` | Agents + job subcollections |
| Secrets | Secret Manager **names** | `enrollment-key`, `admin-token` |
| Student agent | Python container | Compose on the mgmt LAN |
| Instructor UI | HTML/JS from the same service | Status table + probe button |

Local development uses `STORE_BACKEND=memory` so Firestore is not required.

## Auth

### Agents

1. `POST /v1/agents/enroll` with `student_id` + class `ENROLLMENT_KEY`
2. Controller returns `agent_id` (stable UUID derived from student id) and a random `agent_token`
3. Heartbeat and job calls send `Authorization: Bearer <agent_token>`
4. Re-enroll with the same student id **rotates** the agent token

v1 also accepts the shared enrollment key as a convenience on enroll only. The class key is **rotateable** — treat a leak like a password leak.

Tokens are stored as SHA-256 hex hashes. The raw token is shown once at enroll.

### Instructors

`Authorization: Bearer <ADMIN_TOKEN>` on `/v1/labs*` and the UI’s XHR calls.

The HTML for `/` is public (a token prompt gates the data). **Later hardening:** put Identity-Aware Proxy in front of the instructor UI, keep agent routes (`/v1/agents/*`, `/healthz`) off IAP so home labs can still enroll.

## Data model (Firestore)

Collection `agents/{agent_id}`:

| Field | Purpose |
| --- | --- |
| `student_id` | Sheridan email or student number |
| `token_hash` | SHA-256 of agent token |
| `hostname`, `sw_version`, `mgmt_ip`, `serial`, `model` | Last heartbeat |
| `ok`, `last_error` | Last PAN-OS query result |
| `last_seen`, `enrolled_at` | UTC timestamps |

Subcollection `agents/{agent_id}/jobs/{job_id}`:

| Field | Purpose |
| --- | --- |
| `type` | `probe` in v1 |
| `status` | `pending` → `running` → `done` / `error` |
| `created_at`, `completed_at` | UTC |
| `result`, `error` | Agent-posted outcome |

**Never stored:** `FW_API_KEY`, PAN admin passwords, student home public IPs beyond what the student chooses to send as `mgmt_ip`.

## Agent loop

Default interval: 30 seconds.

1. Query PAN-OS `show system info` via XML API (`type=op`)
2. `POST /v1/agents/{id}/heartbeat` with hostname, version, mgmt IP, serial/model, ok/error
3. `GET /v1/agents/{id}/jobs` — pending jobs are claimed (`running`)
4. If type is `probe`, run the same system-info query and `POST` the result

`FW_VERIFY_TLS` defaults to `false` because lab PA-VMs use self-signed management certs.

`FW_HOST=mock` (or `mock://`) makes the agent return canned system info so instructors can smoke-test the controller without a firewall.

## Online / offline

A lab is **online** when `last_seen` is newer than `OFFLINE_AFTER_SEC` (default 120s ≈ two missed heartbeats at 30s + slack). Older or missing `last_seen` is **offline**. A recent heartbeat with `ok=false` is still online (agent is up; the firewall query failed) and `last_error` explains why.

## IAM (GCP)

Cloud Run default compute service account needs:

- `roles/datastore.user` on project `firewall-ai`
- `roles/secretmanager.secretAccessor` on secrets `enrollment-key` and `admin-token`

The human/CI deployer needs Cloud Run Admin, Service Account User, Cloud Build / Artifact Registry write, and (one-time) Firestore + Secret Manager create.

Cloud Run is deployed `--allow-unauthenticated` so student agents at home can call it. Admin routes still require `ADMIN_TOKEN`.

## API

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/` | none (UI); data via admin token |
| `GET` | `/healthz` | none |
| `POST` | `/v1/agents/enroll` | enrollment key |
| `POST` | `/v1/agents/{id}/heartbeat` | agent token |
| `GET` | `/v1/agents/{id}/jobs` | agent token |
| `POST` | `/v1/agents/{id}/jobs/{job_id}/result` | agent token |
| `GET` | `/v1/labs` | admin token |
| `POST` | `/v1/labs/{student_id}/probe` | admin token |

## Threat notes

- A stolen class enrollment key lets someone enroll a fake student id. Rotate the key; delete bogus agents in Firestore if needed
- A stolen admin token can list labs and enqueue probes (probes still execute only on the student’s agent)
- Heartbeat `mgmt_ip` is student-asserted, not a reachable path for the controller
- Do not log request bodies that might contain keys; the controller rejects unknown fields such as `api_key` / `fw_api_key`
