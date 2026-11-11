# Verification record

Performed in the Windows workspace with host Python 3.12.10, final image Python 3.12.12, Docker Desktop Linux engine 28.3.2 and Compose 2.39.1. No AWS deployment, provider message, phone notification or Android build was performed. Existing uncommitted repository edits and recording deletions were preserved.

| Area | Result |
|---|---|
| Automated API/database/alerts/deployment tests | **26 passed in 8.17 seconds** inside the final non-root Linux image, with isolated PostgreSQL 16.8 and Redis 7.4.2 on a private Docker test network |
| Actual Redis/Celery transport | Passed with a real Celery test worker: dispatcher publishes durable fake alert, worker records delivered/attempt 1, and harmless probe completes |
| Incident/outbox atomicity | Passed; forced outbox insert failure rolls back incident |
| Broker failure recovery | Passed with failed publish followed by automatic redispatch of durable pending row |
| Bounded publication / lost queue recovery | Passed; repeated scans respect the dispatch lease and lost messages re-publish after lease expiry |
| Duplicate/concurrent processing | Passed; one provider invocation under competing tasks and no resend after delivered |
| Retry limits/crash recovery | Passed; persisted attempts, deferred retry, interrupted attempt recovery and terminal fifth attempt |
| Existing API behavior/auth | Passed; legacy fields/thresholds/routes, optional token gate and separate diagnostics token |
| Liveness/readiness | Passed, including redacted database failure and readiness during Redis failure |
| Deployment/rollback control flow | Passed locally using simulated Docker/AWS commands; failed new image restores/verifies prior image |
| Image/release identity | 3 focused deployment tests passed after adding OCI revision verification, including rejecting a mismatched image before migration |
| Compose configurations | Both parse; production default services exclude PostgreSQL, expose only proxy 80/443 and retain model/recording/RDS-CA mounts |
| Model artifact integrity | Passed SHA-256 verification against inspected assets |
| Real model inference | Passed generated one-second silent PCM WAV on Windows and inside Linux application image; score .083875, transcript is a string |
| Linux inference measurement | Final observed run: model load 10.298 s, inference .466 s, process peak RSS 341740 KiB (~334 MiB). Synthetic sample, not a capacity benchmark |
| Dependency vulnerability audit | **No known vulnerabilities found** after fixing Flask/python-dotenv audit findings |
| Python/workflow syntax and editor diagnostics | Valid Python and workflow YAML; no editor diagnostics in backend additions |
| Shell scripts | Bash syntax checks passed |
| Production Nginx TLS configuration | Syntax passed; localhost HTTPS readiness returned ready with a generated, explicitly trusted test certificate; temporary test proxy stopped |
| Full Compose smoke/recreation | **Passed**: all seven runtime services healthy; real inference, both API upstreams, release checks and worker probe pass; PostgreSQL sentinel survives recreation; worker probe and proxy routing pass again after DB/API recreation |
| Container vulnerability scan | **Configured gate passed: 0 fixable HIGH/CRITICAL**. Full report has 1103 findings: 8 CRITICAL, 300 HIGH, 498 MEDIUM, 251 LOW, 46 UNKNOWN. All HIGH/CRITICAL lack a vendor FixedVersion; see triage notes below |
| AWS ECR/EC2/RDS/OIDC/SSM/TLS | Configuration/scripts provided; externally unverified |
| Production provider / Android | Missing in original checkout; cannot exercise absent implementation |

The first image build exposed conflicting parallel exports of the same tag. Compose now builds once through api1 and all roles reuse that image. Initial Nginx health checks exhausted retries before real models loaded; the proxy now waits on API readiness and has a startup grace period. Trivy's initial database download exceeded its default scan deadline; CI and the retry use a 15-minute deadline. These are recorded as verification findings, not successful checks.

The initial dependency audit reported Flask 3.1.2/PYSEC-2026-2151 and python-dotenv 1.1.1/PYSEC-2026-2270; the lock now uses the reported fixed versions 3.1.3 and 1.2.2. scikit-learn 1.7.1 matches the toxicity artifacts, but voice/scream artifacts were serialized with 1.6.1 and still emit InconsistentVersionWarning. Their inference calls remain commented out in the original active algorithm. Validate/retrain those artifacts as a separately reviewed model change before enabling them; loading successfully does not prove prediction accuracy.

An intermediate image had 54 fixable HIGH/CRITICAL OS findings. Python 3.12.12 plus Debian security upgrades removed those fixable findings. The final image reports Debian 12.15. **Passing this gate does not mean the image has no known vulnerabilities.** Before production, review the remaining 308 HIGH/CRITICAL records, their reachability and vendor dispositions, or choose a stricter blocking policy. The eight CRITICAL records are libaom3/CVE-2023-6879, libglib2.0-0/CVE-2026-58016, libmbedcrypto7/CVE-2025-47917, CVE-2026-34873 and CVE-2026-34875, libsqlite3-0/CVE-2025-7458, libxml2/CVE-2026-6653, and zlib1g/CVE-2023-45853. Dispositions include affected, fix_deferred, end_of_life and will_not_fix; none is silently exempted as a false positive. CI retains the complete JSON report and blocks every fixable HIGH/CRITICAL finding. Local raw output is in the ignored .scan-results/container-scan.json scratch report.

The recreation check exposed stale worker connections after a database restart. Checkout now validates, discards a stale connection and reconnects once before application SQL; the completed recreation test verifies worker recovery. Docker Desktop also became unresponsive during a heavy rebuild (`rpc error: ... error reading from server: EOF`). It recovered after restarting Docker and building with application containers stopped. A sandbox disk reading of zero was misleading; a host-level check showed about 20 GiB free. Temporary test virtual-environment/database files were removed, and disposable test containers were stopped. The application named volumes were preserved.

## Reproduce the automated suite

Use only a disposable database; fixtures truncate contacts/incidents/outbox/attempts/check rows.

```powershell
$env:RUN_INTEGRATION='true'
$env:RUN_REDIS='true'
$env:DATABASE_URL='postgresql://shield:test-only@127.0.0.1:55432/shield_test'
$env:REDIS_URL='redis://127.0.0.1:56379/0'
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\python.exe -m scripts.inference_check
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt --disable-pip --no-deps
```

Create the disposable localhost test services and Python environment using the [runbook](deployment.md) before running these commands; install pip-audit separately as shown there. Final verification used the same PostgreSQL/Redis image versions on a private Docker test network without published ports. All disposable test services were stopped after verification. The Compose application database is separate and is not truncated by this suite. The local application stack remains running at http://localhost:8080 with its named volumes preserved.
