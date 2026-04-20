import psycopg2

conn = psycopg2.connect(
    dbname="aishield",
    user="postgres",
    password="postgres",
    host="localhost",
    port="5432"
)

cursor = conn.cursor()

cursor.execute("""
INSERT INTO incidents
(user_id, threat_score, threat_level, speech_text, emotion, audio_path, latitude, longitude, status)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", (1, 0.75, "LEVEL_2", "help me please", "fear", "audio/test.wav", 17.385, 78.486, "ACTIVE"))

conn.commit()
cursor.close()
conn.close()

print("Inserted successfully")