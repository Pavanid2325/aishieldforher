from vosk import Model, KaldiRecognizer
import sounddevice as sd
import json
from toxicity_predict import predict_toxicity

model = Model(r"C:\Users\hp\Desktop\PROJECTS\aishield4for\aishieldforher\vosk-model-small-en-in-0.4")

#downloaded from https://alphacephei.com/vosk/models
#vosk-model-small-en-us-0.15	40M	9.85 (librispeech test-clean) 10.38 (tedlium)	Lightweight wideband model for Android and RPi	Apache 2.0

rec = KaldiRecognizer(model, 16000)

def compute_threat_score(scores):
        return (
        0.4 * scores["threat"] +
        0.2 * scores["toxic"] +
        0.15 * scores["insult"] +
        0.15 * scores["obscene"] +
        0.1 * scores["severe_toxic"]
    )

distress_keywords = [
    "help", "save me", "leave me", "stop",
    "don't touch", "please help", "i am scared"
]

def keyword_score(text):
    score = 0
    for word in distress_keywords:
        if word in text:
            score += 1
    return min(score / 3, 1.0)

def callback(indata, frames, time, status):
    if rec.AcceptWaveform(bytes(indata)):
        result = json.loads(rec.Result())
        text = result["text"]
        print("Speech:", text)
        scores = predict_toxicity(text)
        print("Toxicity scores:", scores)

        threat_score = compute_threat_score(scores)
        k_score = keyword_score(text)

        final_score = 0.7 * threat_score + 0.3 * k_score

        print("Final Threat Score:", final_score)

        if final_score > 0.6:
            print("⚠ THREAT DETECTED")

    else:
        partial = json.loads(rec.PartialResult())
        print("Listening:", partial["partial"])

with sd.RawInputStream(samplerate=16000, blocksize = 8000, dtype='int16',
                       channels=1, callback=callback):
    print("Listening...")
    while True:
        pass
