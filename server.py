from fileinput import filename

from flask import Flask, request, jsonify
from toxicity_predict import predict_toxicity
import toxicity_predict
from stt import iot_score, process_audio_file
import os
import time
import numpy as np
from db import insert_incident
import os
import hashlib
import json
from datetime import datetime
from dotenv import load_dotenv
import psycopg2


load_dotenv()


app = Flask(__name__)
audio_buffer = []


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
last_saved_time = 0


def get_threat_level(threat_score):
    if threat_score < 0.4:
        return "IDLE"
    elif threat_score < 0.6:
        return "LEVEL_1"
    elif threat_score < 0.8:
        return "LEVEL_2"
    return "LEVEL_3"

def parse_coordinate(value):
    if value in (None, "", "null"):
        return 0.0
    return float(value)

def generate_hash(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()

def store_incident_details(threat_score, level, text, audio_path, lat, lon):

    print("Saving to DB...")

    # 🔐 Prepare data for hashing
    data = {
        "threat_score": threat_score,
        "level": level,
        "text": text,
        "lat": lat,
        "lon": lon
    }

    hash_value = generate_hash(data)

    insert_incident(
        user_id=1,
        threat_score=float(threat_score),
        level=level,
        text=text,
        emotion="unknown",
        audio_path=audio_path,
        lat=parse_coordinate(lat),
        lon=parse_coordinate(lon),
        hash=hash_value   
    )

def insert_contact(name, phone, level):
    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO contacts (name, phone, level) VALUES (%s, %s, %s)",
        (name, phone, level)
    )

    conn.commit()
    cursor.close()
    conn.close()

@app.route("/stream_audio", methods=["POST"])
def stream_audio():
    try:
        audio_bytes = request.data
        lat = float(request.args.get("latitude", 0))
        lon = float(request.args.get("longitude", 0))
        # hr = float(request.args.get("hr", 0))
        # accel = float(request.args.get("accel", 0))

        if not audio_bytes:
            return jsonify({"error": "No audio data"}), 400

        import wave, time, os

        timestamp = str(int(time.time() * 1000))
        wav_filepath = os.path.join(UPLOAD_FOLDER, f"chunk_{timestamp}.wav")

        # 🔥 PCM → WAV
        with wave.open(wav_filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)

        print("WAV saved:", wav_filepath)

        # 🔥 PROCESS DIRECTLY (NO BUFFER)
        threat_score, text = process_audio_file(wav_filepath)

        # iot = iot_score(hr, accel)

        # final_score = (0.9*threat_score) + (0.3 * iot)
        final_score = threat_score

        level = get_threat_level(final_score)

        # 🔥 SAVE WITH COOLDOWN
        global last_saved_time
        current_time = time.time()

        if threat_score > 0.2 and (current_time - last_saved_time > 15):
            store_incident_details(
                threat_score=final_score,
                level=level,
                text=text,
                audio_path=wav_filepath,
                lat=lat,
                lon=lon
            )
            last_saved_time = current_time

        return jsonify({
            "threat_score": final_score,
            "text": text,
            "level": level
        })

    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500 

from flask import jsonify
import psycopg2

@app.route("/get_contacts", methods=["GET"])
def get_contacts():
    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, phone, level FROM contacts ORDER BY id DESC")
    rows = cursor.fetchall()

    contacts = []
    for row in rows:
        contacts.append({
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "level": row[3]
        })

    cursor.close()
    conn.close()

    return jsonify(contacts)

@app.route("/add_contact", methods=["POST"])
def add_contact():
    data = request.json

    name = data.get("name")
    phone = data.get("phone")
    level = data.get("level")

    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO contacts (name, phone, level) VALUES (%s, %s, %s)",
        (name, phone, level)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "added"})

@app.route("/delete_contact/<int:id>", methods=["DELETE"])
def delete_contact(id):
    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM contacts WHERE id=%s", (id,))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "deleted"})

@app.route("/update_contact/<int:id>", methods=["PUT"])
def update_contact(id):
    data = request.json

    name = data.get("name")
    phone = data.get("phone")
    level = data.get("level")

    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE contacts SET name=%s, phone=%s, level=%s WHERE id=%s",
        (name, phone, level, id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "updated"})

@app.route("/get_contacts_by_level/<int:level>", methods=["GET"])
def get_contacts_by_level(level):
    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
    cursor = conn.cursor()

    if level == 1:
        cursor.execute("SELECT phone FROM contacts WHERE level = 1")

    elif level == 2:
        cursor.execute("SELECT phone FROM contacts WHERE level IN (1,2)")

    else:
        cursor.execute("SELECT phone FROM contacts WHERE level IN (1,2,3)")

    rows = cursor.fetchall()

    phones = [row[0] for row in rows]

    cursor.close()
    conn.close()

    return jsonify(phones)

@app.route("/delete_incident/<int:id>", methods=["DELETE"])
def delete_incident(id):
    try:
        conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM incidents WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Deleted successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_incidents", methods=["GET"])
def get_incidents():
    conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, timestamp, threat_score, threat_level,
           speech_text, latitude, longitude, hash
    FROM incidents
    ORDER BY timestamp DESC
""")

    rows = cursor.fetchall()

    incidents = []
    for row in rows:
        incidents.append({
            "id": row[0],
            "timestamp": str(row[1]),
            "threat_score": row[2],
            "threat_level": row[3],
            "text": row[4],
            "latitude": row[5],
            "longitude": row[6],
            "hash": row[7]
        })

    cursor.close()
    conn.close()

    return jsonify(incidents)


@app.route("/")
def home():
    return "Server Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
