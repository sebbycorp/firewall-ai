# GCP deploy — project `firewall-ai`

Default region: **`northamerica-northeast2` (Toronto)** for Cloud Run and Firestore Native.

If Toronto is blocked by quota or org policy, rerun both scripts with `REGION=us-central1`.

## Prerequisites

- `gcloud` authenticated as someone who can administer project `firewall-ai`
- Billing enabled on the project

## One-time setup

```bash
./infra/setup.sh
```

This enables APIs, creates the default Firestore Native database (if missing), creates Secret Manager secrets named `enrollment-key` and `admin-token` (values entered interactively), and grants the Cloud Run default compute service account:

| Role | Why |
| --- | --- |
| `roles/datastore.user` | Read/write agent documents and jobs |
| `roles/secretmanager.secretAccessor` on those two secrets | Inject env vars at runtime |

Deployer identity also needs (typically Project Owner / Editor in a class project, or):

- `roles/run.admin`
- `roles/iam.serviceAccountUser`
- `roles/cloudbuild.builds.editor`
- `roles/artifactregistry.writer`
- `roles/datastore.owner` (first-time database create)
- `roles/secretmanager.admin` (first-time secret create)
- `roles/serviceusage.serviceUsageAdmin` (enable APIs)

## Deploy

```bash
./infra/deploy.sh
```

Cloud Run is given **Secret Manager names**, not values:

```
ENROLLMENT_KEY=enrollment-key:latest
ADMIN_TOKEN=admin-token:latest
```

`--allow-unauthenticated` is required so student agents at home can call `/v1/agents/*`. Instructor routes still require `ADMIN_TOKEN`. Identity-Aware Proxy on `/` is a later hardening step (see `docs/design.md`).

## Rotate class keys

```bash
printf '%s' 'new-value' | gcloud secrets versions add enrollment-key --data-file=-
printf '%s' 'new-value' | gcloud secrets versions add admin-token --data-file=-
gcloud run services update firewall-ai-controller \
  --region=northamerica-northeast2 \
  --update-secrets=ENROLLMENT_KEY=enrollment-key:latest,ADMIN_TOKEN=admin-token:latest
```

Tell students the new enrollment key. Re-enroll rotates each agent token automatically on next start.
