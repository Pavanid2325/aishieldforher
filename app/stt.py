import os
from app.model_paths import model_root
def asset(path):
    return str(model_root() / path)
import wave
import json
import subprocess
import joblib
from vosk import Model, KaldiRecognizer
from app.toxicity_predict import predict_toxicity
from app.utils import extract_features,extract_features_scream

# Load models
emotion_model, encoder = joblib.load(asset("voice_model/model.pkl"))
text_model = Model(asset("vosk-model-small-en-in-0.4"))
scream_model = joblib.load(asset("scream_model/model.pkl"))

distress_keywords = [
    "help", "save", "leave me", "stop",
    "don't touch", "please", "i am scared","no","kill","killing",
    "shoot","don't","harass"
]

def keyword_score(text):
    score = 0
    for word in distress_keywords:
        if word in text:
            score += 1
    return min(score / 3, 1.0)

def calculate_iot_threat(accel):
    if accel > 15:
        return 1.0
    elif accel > 10:
        return 0.7
    elif accel > 5:
        return 0.4
    else:
        return 0.1

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
            return 0.1
        elif label == "sad":
            return 0.4
        else:
            return 0.1
    return 0.0

def scream_from_audio(audio_path):
    features = extract_features_scream(audio_path)

    if features is not None:
        prediction = scream_model.predict([features])[0]

    else:
        print("Error processing audio")
        return 0
    return prediction


def process_audio_file(audio_path,accel = 0):
    # Convert audio
    if audio_path.endswith(".3gp"):
        print("Converting 3gp â†’ wav")
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

    # Speech must never be logged.

    # # Toxicity score
    # scores = predict_toxicity(text_result)
    # toxicity_score = (
    #     0.2 * scores["threat"] +
    #     0.2 * scores["toxic"] +
    #     0.15 * scores["insult"] +
    #     0.15 * scores["obscene"] +
    #     0.1 * scores["severe_toxic"]
    # )

    # # Keyword score
    # k_score = keyword_score(text_result)

    # # Emotion score
    # emotion_score = emotion_from_audio(audio_path)
    # scream_score = scream_from_audio(audio_path)
    # iot_score = calculate_iot_threat(accel)
    iot_score = 0.1000
    toxicity_score = 0.0555
    k_score = 0
    emotion_score = 0.2
    scream_score = 0

    final_score = (
        0.25 * toxicity_score +
        0.15 * k_score +
        0.25 * emotion_score +
        0.15 * scream_score +
        0.20 * iot_score
    )

    # print("Toxicity:", toxicity_score)
    # print("Keyword:", k_score)
    # print("Emotion:", emotion_score)
    # print("Scream:", scream_score)
    # print("IOT score:",iot_score)
    print("Final Threat Score:", final_score)

    return final_score, text_result
