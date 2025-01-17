import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.extensions import connection

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