from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.extensions import connection
from datetime import datetime
import os
from dotenv import load_dotenv
from flask.typing import ResponseReturnValue

load_dotenv()
app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'your_database'),
    'user': os.getenv('DB_USER', 'your_username'), 
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', ''),
    'port': os.getenv('DB_PORT', '5432')
}

def get_db_connection() -> connection:
    return psycopg2.connect(**DB_CONFIG)

def init_db():
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

# Initialize database on startup
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize database: {e}")

@app.route('/')
def hello_world() -> str:
    return 'Hello, World!'

@app.route('/webhook', methods=['POST'])
def webhook() -> ResponseReturnValue:
    try:
        payload = request.get_json()
        
        if not payload:
            return jsonify({'error': 'No payload received'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO webhook_messages (payload, timestamp) VALUES (%s, %s) RETURNING id',
                    (psycopg2.extras.Json(payload), datetime.utcnow())
                )
                webhook_id = cur.fetchone()[0]
                conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook received and stored',
            'id': webhook_id
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to process webhook',
            'message': str(e)
        }), 500

@app.route('/messages', methods=['GET'])
def get_messages() -> ResponseReturnValue:
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('''
                    SELECT id, payload, timestamp 
                    FROM webhook_messages 
                    ORDER BY timestamp DESC
                ''')
                messages = [dict(row) for row in cur.fetchall()]
        
        return jsonify(messages)
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve messages',
            'message': str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(debug=True, host=host, port=port)
