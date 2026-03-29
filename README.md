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



--mobile app
-


AIShield for HER
│
├── Android App
│     ├── Microphone
│     ├── Vosk STT
│     ├── Python Model (Chaquopy)
│     ├── Threat Score Engine
│     ├── SMS Alert
│     ├── Location Tracking
│     ├── Bluetooth ESP32
│     └── Video Recording
│
├── Python Model
│     ├── toxicity_predict.py
│     ├── models.pkl
│     └── training scripts
│
└── Hardware
      ├── ESP32
      ├── Accelerometer
      ├── Heart Rate Sensor