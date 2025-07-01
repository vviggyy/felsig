import sqlite3
from datetime import date, datetime
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.expanduser("~/telegram_daily_messages.db")
OBS_PATH = os.getenv("OBS_PATH")
TODAY = str(date.today())

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def main():
    if not OBS_PATH:
        log("OBS_PATH not set. Exiting.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT id, text FROM messages WHERE processed = 0 ORDER BY timestamp ASC;")
        rows = cursor.fetchall()

        if not rows:
            log("No new messages.")
            return

        log(f"Processing {len(rows)} messages...")

        note_path = os.path.join(OBS_PATH, f"{TODAY}.md")
        with open(note_path, "a") as f:
            for row_id, message in rows:
                f.write(f"\n- {message}")
                cursor.execute("UPDATE messages SET processed = 1 WHERE id = ?;", (row_id,))

        conn.commit()
        log("Messages written to daily note.")

    except Exception as e:
        log(f"ERROR: {e}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
