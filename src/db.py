import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.extensions import connection
from datetime import datetime

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'your_database'),
    'user': os.getenv('DB_USER', 'your_username'), 
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', ''),
    'port': os.getenv('DB_PORT', '5432')
}


def get_db_connection() -> connection:
    return psycopg2.connect(**DB_CONFIG)


def init_db() -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS webhook_messages (
                    id SERIAL PRIMARY KEY,
                    payload JSONB NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        conn.commit()

def get_messages_from_db() -> list[dict]:
    print(f"getting it")

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('''
                SELECT id, payload, timestamp 
                FROM webhook_messages 
                ORDER BY timestamp DESC
            ''')
            # messages = [dict(row) for row in cur.fetchall()]
            messages = [
                    {
                        'id': row[0],
                        'payload': row[1],
                        'timestamp': row[2].isoformat()
                    }
                    for row in cur.fetchall()
                ]

    print(f"messages are {messages}")
    return messages

def store_message(payload: dict) -> int:  
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO webhook_messages (payload, timestamp) VALUES (%s, %s) RETURNING id',
                (psycopg2.extras.Json(payload), datetime.utcnow())
            )
            message_id = cur.fetchone()[0]
            conn.commit()
    print(f"message_id is {message_id}, payload is {payload}")
    return message_id