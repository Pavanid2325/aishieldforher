from fileinput import filename

from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException


from inference import calculate_iot_threat, process_audio_file
import os
import time

from db import insert_incident, connect
import os
import hashlib
import json
from datetime import datetime
from dotenv import load_dotenv
import psycopg2


load_dotenv()


from operations import create_operations_app, incident_alert_status
from flask import g
app = create_operations_app()
app.config['REQUIRE_MODELS'] = True
from inference import initialize
initialize(app)
app.logger.info(json.dumps({'event':'api_started','release':os.getenv('RELEASE_ID','development')}))
audio_buffer = []


UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
last_saved_time = 0


def get_threat_level(threat_score):
    if threat_score < 0.005:
        return "IDLE"
    elif threat_score < 0.02:
        return "LEVEL_1"
    elif threat_score < 0.05:
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

    app.logger.info('{"event":"incident_persisting"}')
    data = {
        "threat_score": threat_score,
        "level": level,
        "text": text,
        "lat": lat,
        "lon": lon
    }

    hash_value = generate_hash(data)

    return insert_incident(
        user_id=1,
        threat_score=float(threat_score),
        level=level,
        text=text,
        emotion="unknown",
        audio_path=audio_path,
        lat=parse_coordinate(lat),
        lon=parse_coordinate(lon),
        correlation_id=g.request_id, hash=hash_value   
    )

def insert_contact(name, phone, level):
    conn = connect()
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
    

        if not audio_bytes:
            return jsonify({"error": "No audio data"}), 400

        import wave, time, os

        timestamp = __import__("uuid").uuid4().hex
        wav_filepath = os.path.join(UPLOAD_FOLDER, f"chunk_{timestamp}.wav")
        with wave.open(wav_filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)

        
        accel = float(request.args.get("accel", 0))
        threat_score, text = process_audio_file(wav_filepath,accel)

        # iot = iot_score(hr, accel)

        # final_score = (0.9*threat_score) + (0.3 * iot)
        final_score = threat_score

        level = get_threat_level(final_score)
        incident_id = None
        if threat_score > 0.2:
            incident_id = store_incident_details(
                threat_score=final_score,
                level=level,
                text=text,
                audio_path=wav_filepath,
                lat=lat,
                lon=lon
            )

        return jsonify({
            "threat_score": final_score,
            "text": text,
            "incident_id": incident_id,
            "alert_status": incident_alert_status(incident_id),
            "level": level
        })

    except HTTPException:
        raise
    except Exception as e:
        app.logger.error('{"event":"request_failed"}')
        return jsonify({"error": "Request failed"}), 500 

from flask import jsonify
import psycopg2

@app.route("/iot_data", methods=["POST"])
def iot_data():
    try:
        data = request.json
        accel = float(data.get("accel", 0))
        iot_score = calculate_iot_threat(accel)

        return jsonify({
            "accel": accel,
            "iot_score": iot_score,
            "level": get_threat_level(iot_score)
        })

    except Exception as e:
        return jsonify({"error": "Request failed"}), 500
    
@app.route("/get_contacts", methods=["GET"])
def get_contacts():
    conn = connect()
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

    conn = connect()
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
    conn = connect()
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

    conn = connect()
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
    conn = connect()
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
        conn = connect()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM incidents WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Deleted successfully"})

    except Exception as e:
        return jsonify({"error": "Request failed"}), 500

@app.route("/get_incidents", methods=["GET"])
def get_incidents():
    conn = connect()

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
