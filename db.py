import psycopg2
from sqlalchemy import values

conn = psycopg2.connect(
    dbname="aishield",
    user="postgres",
    password="YOUR_PASSWORD",
    host="localhost",
    port="5432"
)

def insert_incident(user_id, threat_score, level, text, emotion, audio_path, lat, lon, hash):
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO incidents
            (user_id, threat_score, threat_level, speech_text, emotion, audio_path, latitude, longitude, status, hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, threat_score, level, text, emotion, audio_path, lat, lon, "ACTIVE", hash))

        conn.commit()

    except Exception as e:
        print("DB ERROR:", e)
        conn.rollback()

    finally:
        cursor.close()
        conn.close()
