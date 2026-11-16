# Runbook

## Local startup

Run from the Git/backend root (the directory containing compose.yaml). Requires Docker Desktop in Linux-container mode, Compose >=2.24.4 (production uses !override), and the checked-in trusted model assets. Python 3.12 matches the existing Python 3.12 bytecode evidence; the new lock records the complete dependency resolution. Gunicorn/Celery production prefork run in Linux containers, not native Windows.

Do not overwrite your existing .env. Create the separate local file:

```powershell
Copy-Item .env.example .env.local
docker compose --env-file .env.local build
docker compose --env-file .env.local up -d --wait postgres redis
docker compose --env-file .env.local run --rm --no-deps migrate
docker compose --env-file .env.local up -d --wait api1 api2 worker dispatcher nginx
curl.exe --fail http://localhost:8080/health/live
curl.exe --fail http://localhost:8080/health/ready
docker compose --env-file .env.local run --rm --no-deps api1 python scripts/smoke.py http://nginx
docker compose --env-file .env.local logs --tail 100 worker dispatcher
docker compose --env-file .env.local exec worker celery -A app.alerts:celery inspect ping
docker compose --env-file .env.local exec dispatcher python scripts/check_dispatcher.py
docker compose --env-file .env.local exec -T postgres psql -U shield -d shield -c "SELECT status,count(*),min(created_at) AS oldest FROM alert_outbox GROUP BY status;"
```

Use the example diagnostic token only locally: `curl.exe -H "Authorization: Bearer local-diagnostics-change-me" http://localhost:8080/ops/instance`. Repeated authenticated requests demonstrate api1/api2. No API, Redis or database host ports are published. For Android emulator/device USB debugging: `adb reverse tcp:8080 tcp:8080`. Normal root route remains `Server Running`.

Asset paths in MODEL_ASSET_DIR must contain toxicity, voice_model, scream_model and vosk-model-small-en-in-0.4. Model files are excluded from the image and mounted read-only. [model-assets.sha256](../assets/model-assets.sha256) ties these mounts to the inspected source artifacts. Copy the model subdirectories from the same reviewed checkout to EC2 `/opt/aishield/models-bundle`; retain the manifest and verify before deployment with `python -m scripts.verify_models` and MODEL_ROOT pointing at the bundle. Do not download or load untrusted pickle files. Updating assets requires a reviewed manifest change and inference validation.

For a fast deployment-mechanics demo, set FAKE_INFERENCE=true in .env.local; the explicit synthetic model is forbidden in production. Real scoring is currently fixed below persistence threshold, so normal recordings do not create alerts (see [evidence](architecture.md)). The fake alert provider never contacts a phone or external service. To see its durable statuses, run the integration tests below; they inject a .3 threat score and fake contact.

## Testing

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Integration tests **truncate** their configured test database; never supply a development or production URL. With a separate PostgreSQL/Redis test instance:

```powershell
$env:DATABASE_URL='postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:55432/shield_test'
$env:REDIS_URL='redis://127.0.0.1:56379/0'
$env:RUN_INTEGRATION='true'
$env:RUN_REDIS='true'
.\.venv\Scripts\python.exe -m pytest -q
```

To create those disposable services locally (not needed for the application's Compose database):

```powershell
docker run -d --rm --name shield-test-postgres -e POSTGRES_USER=shield -e POSTGRES_PASSWORD=test-only -e POSTGRES_DB=shield_test -p 127.0.0.1:55432:5432 postgres:16.8-alpine
docker run -d --rm --name shield-test-redis -p 127.0.0.1:56379:6379 redis:7.4.2-alpine
do { Start-Sleep -Seconds 1; docker exec shield-test-postgres pg_isready -U shield -d shield_test } while ($LASTEXITCODE -ne 0)
$env:DATABASE_URL='postgresql://shield:test-only@127.0.0.1:55432/shield_test'
$env:REDIS_URL='redis://127.0.0.1:56379/0'
$env:RUN_INTEGRATION='true'
$env:RUN_REDIS='true'
.\.venv\Scripts\python.exe -m pytest -q
docker stop shield-test-postgres shield-test-redis
```

The live broker test runs a real Celery test worker against the isolated Redis instance. The other alert tests run tasks directly with PostgreSQL and mock only transport/provider calls; they validate atomic persistence, cooldown, re-publication, retry budget and session-lock contention. Shell deployment tests use fake Docker/AWS programs to exercise promotion and rollback without cloud calls. They require Bash (Git Bash supported on Windows).

On Linux/Git Bash, `RUNTIME_ENV_FILE=.env.local bash scripts/compose-check.sh` builds, starts the stack, migrates once, verifies readiness and both upstreams, performs a harmless worker probe, recreates PostgreSQL/API containers, checks a persisted sentinel row, then probes routing again. It preserves volumes and leaves the stack running. CI invokes this with fake inference/provider and isolated Compose volumes. Stop with `docker compose --env-file .env.local down` (no `-v`).

Install the audit tool with `python -m pip install pip-audit==2.9.0`, then run `python -m pip_audit -r requirements.txt`; every advisory blocks CI. Container scan uses Trivy fixable HIGH/CRITICAL as blocking findings; unfixed findings remain reported for triage. There are no silent advisory exclusions. A failing scan prevents publication, even if application tests pass. The current report contains unfixed HIGH/CRITICAL findings requiring review before production; see [actual results](verification.md). Refresh pins deliberately with pip-tools 7.5.1 (`python -m pip install pip-tools==7.5.1`, then `pip-compile --output-file=requirements.txt requirements.in`) and revalidate the model artifacts. Python, Nginx, Redis, PostgreSQL and Trivy images have version tags; production backend releases are pinned by content digest. Base/sidecar tag mutation and OS package repositories mean rebuilds are not byte-for-byte identical; review digest pinning and scheduled rebuild policy for stricter supply-chain requirements.

## Runtime configuration inventory

See [.env.example](../.env.example) for placeholders. No real secrets are added.

| Variable | Meaning |
|---|---|
| RUNTIME_ENV_FILE | Local .env.local; deployment exports .env |
| APP_ENV | development/test/production; production fail-closed validation |
| DATABASE_URL | PostgreSQL URI, URL-encoded password; production private RDS DNS name |
| POSTGRES_USER / POSTGRES_DB / POSTGRES_PASSWORD | Local PostgreSQL bootstrap only |
| REDIS_URL | Private broker URL; default redis://redis:6379/0 |
| API_TOKEN | Optional local Bearer auth; required production deployment gate |
| DIAGNOSTIC_TOKEN | Separate operator-only Bearer auth for /ops; required production |
| ALERTS_ENABLED | true enables fake local outbox; false required production until adapter exists |
| ALERT_PROVIDER | fake only currently supported, development/CI only |
| FAKE_ALERT_FAIL | true simulates provider failure in development/CI |
| FAKE_INFERENCE | true uses synthetic score/transcript; forbidden production |
| MODEL_ASSET_DIR | Host directory holding mounted model subdirectories |
| MODEL_ROOT | Container /models; optional native-Python artifact directory |
| UPLOAD_FOLDER | Container /data/uploads; optional native recording directory |
| DB_POOL_SIZE | Per-process max connections, default 2 |
| GUNICORN_WORKERS | Per-API process count, default 1; recalculate memory/connections before raising |
| TRUST_PROXY | true only behind the private one-hop Nginx topology |
| BACKEND_IMAGE | Local tag or immutable ECR repository@sha256 digest |
| RELEASE_ID | Commit SHA; set by deploy script |
| INSTANCE_ID | Compose assigns api1/api2; no secret topology details |
| RDS_CA_PATH | In-container /run/rds/global-bundle.pem |
| RDS_CA_DIR | Host directory containing the current AWS RDS CA bundle |
| TLS_DIR | Host directory containing fullchain.pem and privkey.pem |
| PUBLIC_BASE_URL | HTTPS public DNS URL for production smoke checks |
| RUN_INTEGRATION / RUN_REDIS | Test-only opt-in switches for destructive isolated DB tests/live broker |

API/diagnostic tokens and DB password are secrets. AWS_REGION comes from the EC2 AWS CLI region configuration or instance environment. Production requires no provider credential yet because no real provider is implemented. A future adapter must document its exact secret names and permissions.

## AWS setup (manual, creates billable resources only when you execute it)

No AWS resources have been created or changed by this implementation.

1. Choose AWS account/region and a VPC with application connectivity. Create a private subnet group spanning RDS availability zones, with no public access. Create an encrypted PostgreSQL RDS instance, deletion protection, automated backups (e.g. seven days), and a dedicated least-privilege application database user owning only this application's schema. Review the inferred initial schema against an existing DB before running migration. Prefer Multi-AZ if your availability budget permits.
2. Create an application security group for EC2 with TCP 443 inbound from clients and TCP 80 only for redirect/certificate validation. Do not open 22, 5000, 5432 or 6379 publicly. Create a DB security group permitting TCP 5432 **only from the application EC2 security group**, not an internet CIDR. EC2 needs outbound 443 to ECR/SSM/Secrets Manager and 5432 to RDS; use VPC endpoints/NAT where appropriate. Redis and APIs stay on the private Docker network. EC2 is the one public host; RDS has no public endpoint.
3. Create an ECR repository with immutable tags, scan-on-push/enhanced scanning and a lifecycle policy retaining the current and at least two prior successful digests. Store the account registry and repository name as GitHub environment variables. Avoid deleting rollback digests.
4. Provision a Linux amd64 EC2 host sized from measured model RSS/CPU (start with enough memory for two full model copies plus workers, OS and headroom). Install Docker Engine, Compose >=2.24.4, AWS CLI v2, curl, Bash and util-linux/flock. Enable Docker at boot. Enable/update the SSM agent. Attach AmazonSSMManagedInstanceCore and the restricted [EC2 policy](../deploy/ec2-policy.example.json). Restrict Secrets Manager to the one runtime secret; add kms:Decrypt for its exact CMK only if needed. EC2 has no static AWS access keys and needs no ECR write privileges. Configure `aws configure set region YOUR_REGION` for the root/SSM execution context (region is not a credential).
5. Create `/opt/aishield/{deploy,scripts,tls,rds,models-bundle}` owned by the deploy administrator. SSM runs the constrained host deployment command; access to SendCommand is privileged host access and must be restricted to this exact instance and trusted GitHub environment. Copy the reviewed Compose/scripts/deploy configuration there initially; subsequent CI releases copy their own deployment bundle from the validated image. Keep release-directory permissions private. Docker group/root access is operationally privileged.
6. Store the runtime dotenv file in Secrets Manager (SecretString containing dotenv text), or install it with a trusted configuration-management channel. On EC2 use `umask 077; aws secretsmanager get-secret-value --secret-id aishield/runtime --query SecretString --output text > /opt/aishield/.env`. Do not echo it, put it into GitHub output, or source it as shell code. Set APP_ENV=production, ALERTS_ENABLED=false, FAKE_INFERENCE=false, real random API_TOKEN/DIAGNOSTIC_TOKEN, private RDS DATABASE_URL, model directory, RDS/TLS mount directories and HTTPS PUBLIC_BASE_URL. Set RUNTIME_ENV_FILE=.env in the production file. Retain it outside the image and back it up securely. Rotate tokens/passwords using your secret management process and recreate affected containers.
7. Download the official [RDS trust bundle](https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem) to `/opt/aishield/rds/global-bundle.pem` over verified HTTPS. The application forces sslmode=verify-full and that CA file for all production PostgreSQL connections; do not connect through an IP or disable hostname validation. Plan CA rotation. Confirm the RDS endpoint and access security group before migration.
8. Point a DNS A record at an EC2 Elastic IP (or your approved address). Obtain a publicly trusted certificate, e.g. Certbot with DNS validation scoped to the necessary DNS zone, and install fullchain.pem/privkey.pem in the TLS directory. Nginx maps 80/443, redirects HTTP application requests to HTTPS and uses TLS 1.2/1.3. Renewal must update those files and run `docker compose -f compose.yaml -f compose.production.yaml exec nginx nginx -s reload`; verify renewal with a dry run. Certificate issuance/renewal is deliberately not automated with broad DNS credentials in the app. The HTTP liveness route is the sole redirect exception. Test external certificate trust/hostname before release.
9. Create the GitHub OIDC identity provider for `https://token.actions.githubusercontent.com` with audience sts.amazonaws.com. Create a deployment role using [trust template](../deploy/oidc-trust.example.json), replacing placeholders with the exact account/owner/repository. Because the job uses environment production, the legacy-format sub is `repo:OWNER/REPOSITORY:environment:production`, not a branch-form sub. For repositories created after July 15, 2026 or opted into immutable subject claims, match the actual subject including immutable owner/repository IDs (for example `repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID:environment:production`) instead of the template's legacy name format. Verify the repository's subject format using [GitHub's OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws); do not replace an exact subject with a wildcard. **Configure that GitHub environment's deployment branch restriction to main**, protect main with required checks/review, and restrict environment administration. This combination restricts repository and deployment branch. Attach [GitHub permissions](../deploy/github-policy.example.json), scoping repository, region and exact EC2 instance. Wildcard actions are avoided; GetAuthorizationToken/GetCommandInvocation require the shown broader resources. For higher assurance, use a custom SSM deployment document rather than general shell execution.
10. Configure production environment variables AWS_DEPLOY_ROLE_ARN, AWS_REGION, ECR_REGISTRY, ECR_REPOSITORY, EC2_INSTANCE_ID. Require the checks job in branch protection. PR jobs have contents:read only and no production environment/OIDC permission. Only a trusted main push runs the production job. AWS configuration and policies follow [GitHub OIDC guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) and [SSM Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html).

## Deploy and rollback

CI tests first, dependency audits, builds and exercises the Compose image, scans it, exports that exact image as an Actions artifact, then the trusted production job loads it, tags it with the commit SHA and publishes it. The build records GITHUB_SHA in the OCI image revision label; deployment rejects any digest whose label does not match the requested release. For manually built production images, pass `--build-arg SOURCE_REVISION=FULL_40_CHAR_COMMIT_SHA`. It resolves the ECR digest and sends the immutable digest to EC2 through SSM. No second image build occurs. Artifact upload/download integrity is managed by Actions; production deploy concurrency is serialized both in GitHub and by host flock.

On the EC2 host (manual commands, after setup):

```bash
cd /opt/aishield
bash scripts/deploy.sh ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPOSITORY@sha256:FULL_DIGEST FULL_40_CHAR_COMMIT_SHA
docker compose -f compose.yaml -f compose.production.yaml ps
curl --fail https://YOUR_DNS_NAME/health/ready
bash scripts/rollback.sh
```

Use a 12-digit account ID in the actual deploy command; placeholders above must be replaced. The script validates digest/SHA, required Compose and runtime configuration, records the old successful release, authenticates using the EC2 role, pulls the image, validates production settings, runs migrations once, replaces containers, tests public HTTPS readiness/routing/release/worker round-trip and dispatcher heartbeat, then atomically records success. A failed post-validation application deployment restores the previous image and verifies it; failure remains a nonzero exit even after successful rollback. Initial deployment has no previous image. Failed rollback prints an explicit operator-action message. SSM status is polled by CI and must be Success to finish the workflow.

This is an in-place deployment with brief interruption, **not zero downtime**. Nginx refreshes Docker DNS after replacement, but connections can fail during recreation or model loading. Data volumes are preserved; no deployment command deletes volumes. Production infrastructure config is copied from the new image before deployment; automatic rollback restores the previous application image, not an arbitrary prior incompatible Nginx/Compose topology. Keep infrastructure changes backward-compatible or restore their reviewed backup manually as well.

Migrations are checksummed, serialized, transactional, additive and forward-only. Existing migration files cannot be edited after use. API/worker startup never runs migrations. Rollback does not undo schema changes; only previous images compatible with the expanded schema are safe. Back up/test restoration before risky schema changes, use expand/contract releases, and never automatically reverse destructive migrations. The original pre-DevOps image had no image/release history and is not an automatic rollback target.

## Database/evidence backup and restore

Enable RDS automated backups/PITR and take a manual snapshot before schema releases. Test restoration into a **new private RDS instance**, verify counts and application compatibility, then switch DATABASE_URL through the secret and redeploy. Do not overwrite the live instance during a restore rehearsal. Protect backup data as personal/safety-sensitive information.

For local SQL backups (Bash examples, archive may contain contacts/transcripts/GPS):

```bash
umask 077
docker compose --env-file .env.local exec -T postgres pg_dump -U shield -d shield -Fc > shield-backup.dump
# Restore to a separate pre-created database, never the active application's database:
docker compose --env-file .env.local exec -T postgres createdb -U shield shield_restore
docker compose --env-file .env.local exec -T postgres pg_restore -U shield -d shield_restore --no-owner < shield-backup.dump
```

For RDS use pg_dump/pg_restore from a trusted host inside the private network with PGSSLMODE=verify-full, PGSSLROOTCERT pointing to the CA bundle and credentials supplied through a protected PGPASSFILE. Match PostgreSQL client/server major versions. Back up the recordings volume separately to encrypted storage with a retention policy; database snapshots do not include audio files. Restore both when evidence paths need to remain usable. Do not use `docker compose down -v`, `docker volume prune`, or destructive schema downgrades as deployment cleanup.

## Remaining release gates

Recover Android source and verify its build URL/auth/async status handling on a real device. Implement and verify the actual alert provider and idempotency semantics before enabling production notifications. Review the original database DDL/user ownership and any data migration from hard-coded user 1. Verify real audio inference with the trusted artifact environment. Exercise the complete Linux Compose stack, TLS certificate, AWS OIDC/ECR/SSM deployment and a rollback rehearsal before calling the environment production-ready. See [verification results](verification.md) for what was actually exercised in this session.
