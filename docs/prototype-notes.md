# Earlier prototype notes

These are historical ideas and setup notes, not the current deployed behavior. See [architecture](./architecture.md) for the implementation.

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
