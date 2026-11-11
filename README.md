# AI Shield for Her

This checkout contains the Flask/PostgreSQL backend and trusted audio model assets. Android source and a real emergency-message provider are absent. Existing routes and active scoring behavior are preserved; the current scoring inputs are constants and never reach the incident-persistence threshold during ordinary inference.

The DevOps extension runs Nginx, two non-root Gunicorn APIs, Redis, Celery workers, a durable alert dispatcher and PostgreSQL locally. Production uses the same application image on EC2 with private RDS, verified database TLS, HTTPS and GitHub OIDC/SSM deployment. Two API containers provide process redundancy; EC2 remains one host failure point. Fake alert delivery is available locally; production notification delivery is disabled until a real provider adapter exists.

Start with the [local/AWS runbook](docs/deployment.md), [architecture and repository findings](docs/architecture.md), and [executed verification results](docs/verification.md).

```powershell
Copy-Item .env.example .env.local
docker compose --env-file .env.local build
docker compose --env-file .env.local up -d --wait postgres redis
docker compose --env-file .env.local run --rm --no-deps migrate
docker compose --env-file .env.local up -d --wait api1 api2 worker dispatcher nginx
curl.exe --fail http://localhost:8080/health/ready
```

Use a separate disposable database for tests. Never run the integration suite against real incident data. Full commands, environment variables, model mounts, worker inspection, deployment and rollback are in the runbook. The notes below are retained prototype material; several proposed features/thresholds differ from the running code.

## Earlier prototype notes

--ai model
vosk 
jigsaw dataset
-emotion-sound 
-heartbeat
-motion(accelerometer and gyroscope)
-location(AIShield4Her incident reports (timestamp, location, threat_score)
Public crime databases (API integration with police records))
-15 to 30sec video capturing


State: IDLE
  ↓ (threat_score ≥ 0.5)
State: LEVEL_1 (Family Notification)
  ↓ (threat_score ≥ 0.7 AND 30s timeout)
State: LEVEL_2 (Community Alert)
  ↓ (threat_score ≥ 0.85 OR user confirmation)
State: LEVEL_3 (Police Dispatch)



AIShield for HER
│
└── Android App
    ├── Record Audio -
    ├── Upload Audio -
    ├── Receive Threat Score -
    ├── SMS Alerts -
    ├── Location -
    └── Video

└── Flask Server
    ├── Upload API -
    ├── Audio Storage -
    ├── AI Engine
    │       ├── Vosk STT -
    │       ├── Toxicity Model -
    │       ├── Emotion Audio Model -
    │       ├── Keyword Detection -
    │       ├── Sensor data
    │       └── Threat Score Engine       
    └── Database 
        ├── Users
        ├── Contacts
        ├── Incidents
        └── Evidence
└── Hardware
    ├── ESP32
    ├── Accelerometer
    └── Heart Rate Sensor

AIShield App
│
├── Login / Signup
├── Home Dashboard
├── Emergency Contacts
├── Live Monitoring / Recording
├── Incident History
├── Location View
├── Settings / Permissions
└── Profile


To Run android version : python server.py
To run using microphone : python stt.py
run these in cmd before running the server:
    adb devices
    adb reverse tcp:5000 tcp:5000

    
cmd for postgres:
password : postgres
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost
 \c aishield              
 \dt          to get tables
 

## Implemented DevOps extension

Start with the [local and AWS runbook](docs/deployment.md), [repository evidence and architecture](docs/architecture.md), and [actual verification results](docs/verification.md). The older notes above describe prototype intentions; the evidence document distinguishes active scoring from proposed features. No Android source or external alert provider is present in this checkout. Production alert delivery remains disabled until a real adapter is supplied.

