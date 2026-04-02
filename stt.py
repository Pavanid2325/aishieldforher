import wave
import json
import subprocess
import os
import joblib
from vosk import Model, KaldiRecognizer
from toxicity_predict import predict_toxicity
from utils import extract_features

# Load models
emotion_model, encoder = joblib.load("voice_model/model.pkl")
text_model = Model(r"C:\Users\hp\Desktop\PROJECTS\aishield4for\aishieldforher\vosk-model-small-en-in-0.4")

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

def convert_to_wav(input_file):
    output_file = input_file.replace(".3gp", ".wav")

    command = [
        "ffmpeg",
        "-i", input_file,
        "-ar", "16000",
        "-ac", "1",
        output_file
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_file

def emotion_from_audio(audio_path):
    features = extract_features(audio_path)
    if features is not None:
        pred = emotion_model.predict([features])
        label = encoder.inverse_transform(pred)[0]

        if label == "fear":
            return 1.0
        elif label == "angry":
            return 0.7
        elif label == "sad":
            return 0.4
        else:
            return 0.1
    return 0.0

def process_audio_file(audio_path):
    # Convert audio
    if audio_path.endswith(".3gp"):
        print("Converting 3gp → wav")
        audio_path = convert_to_wav(audio_path)

    wf = wave.open(audio_path, "rb")
    rec = KaldiRecognizer(text_model, wf.getframerate())

    text_result = ""

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text_result += " " + result.get("text", "")

    final_result = json.loads(rec.FinalResult())
    text_result += " " + final_result.get("text", "")

    print("Speech Text:", text_result)

    # Toxicity score
    scores = predict_toxicity(text_result)
    toxicity_score = (
        0.4 * scores["threat"] +
        0.2 * scores["toxic"] +
        0.15 * scores["insult"] +
        0.15 * scores["obscene"] +
        0.1 * scores["severe_toxic"]
    )

    # Keyword score
    k_score = keyword_score(text_result)

    # Emotion score
    emotion_score = emotion_from_audio(audio_path)

    # Final hybrid score
    final_score = (
        0.6 * toxicity_score +
        0.2 * k_score +
        0.2 * emotion_score
    )

    print("Toxicity:", toxicity_score)
    print("Keyword:", k_score)
    print("Emotion:", emotion_score)
    print("Final Threat Score:", final_score)

    return final_score, text_result