import sqlite3
import json

def get_row():
    try:
        conn = sqlite3.connect('workspace/lui.db')
        conn.row_factory = sqlite3.Row
        # Try to find an AI-analyzed one, or just get the first one
        row = conn.execute("SELECT * FROM capabilities WHERE domain != 'unknown' LIMIT 1").fetchone()
        if not row:
            row = conn.execute("SELECT * FROM capabilities LIMIT 1").fetchone()
            
        if row:
            data = dict(row)
            # Pretty print for the user
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_row()
