import psycopg2

conn = psycopg2.connect(
    dbname="aishield",
    user="postgres",
    password="YOUR_PASSWORD",
    host="localhost",
    port="5432"
)

def insert_incident(user_id, threat_score, level, text, emotion, audio_path, lat, lon):
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO incidents
        (user_id, threat_score, threat_level, speech_text, emotion, audio_path, latitude, longitude, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (user_id, threat_score, level, text, emotion, audio_path, lat, lon, "ACTIVE"))

    conn.commit()
    cursor.close()