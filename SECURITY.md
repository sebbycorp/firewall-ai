# Security

Firewall AI is an **agent-proxy** lab: the controller never talks to a student firewall, and it never stores a PAN-OS API key.

## What stays on the student machine

- `FW_API_KEY` — PAN-OS XML API key, used only by the local Docker agent
- `FW_HOST` — management IP of the student’s PA-VM
- The agent’s `.env` file

The controller receives only heartbeat metadata (hostname, version, management IP, serial/model, ok/error). It does **not** open a VPN, tunnel, or inbound path into a student’s home network.

## What the controller holds

- Hashed per-agent tokens (not the PAN-OS key)
- Shared class `ENROLLMENT_KEY` and instructor `ADMIN_TOKEN` via Secret Manager **names** at deploy time
- Last-seen status and probe job results in Firestore

## No secrets in git

- Never commit `.env`, service-account JSON, gcloud ADC files, or real tokens
- Examples use `replace-me` / `YOUR_…` placeholders only
- Rotate `ENROLLMENT_KEY` and `ADMIN_TOKEN` between terms (or immediately after a leak)
- If a PAN-OS key is pasted into chat, email, or git, revoke it on the firewall and generate a new one

## Auth model (v1)

- Agents enroll with the class enrollment key and receive a per-agent token
- Instructor UI/API requires `Authorization: Bearer <ADMIN_TOKEN>`
- Cloud Run is publicly reachable so home labs can call home; IAP in front of `/` and `/v1/labs*` is the next hardening step (see `docs/design.md`)
