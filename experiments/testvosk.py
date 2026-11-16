from vosk import Model
from pathlib import Path

model = Model(str(Path(__file__).resolve().parents[1] / "assets/models/vosk-model-small-en-in-0.4"))
print("Model loaded successfully")
