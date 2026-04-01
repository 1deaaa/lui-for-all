import sqlite3
import json

conn = sqlite3.connect('d:/Desktop/lui-for-all/backend/app.db')
c = conn.cursor()
c.execute('SELECT id, content, metadata FROM messages WHERE role="assistant" AND metadata IS NOT NULL ORDER BY created_at DESC LIMIT 5')
rows = c.fetchall()
for row in rows:
    print(f"ID: {row[0]}")
    print(f"Content: {row[1][:50]}")
    print(f"Metadata: {row[2]}")
    print("-" * 40)
conn.close()
