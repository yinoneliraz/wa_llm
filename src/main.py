from flask import Flask, request, Response, jsonify, make_response
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.extensions import connection
from datetime import datetime
import os
from dotenv import load_dotenv
from db import get_db_connection, init_db
load_dotenv()

port = int(os.getenv("PORT", "5001"))
host = os.environ.get("HOST", "0.0.0.0")
print(f"test Running on {host}:{port}")
app: Flask = Flask(__name__)



# Initialize database on startup
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize database: {e}")

@app.route('/')
def hello_world() -> str:
    return 'Hello, World!'

@app.route('/webhook', methods=['POST'])
def webhook() -> Response:

    try:
        payload = request.get_json()
        
        if not payload:
            return make_response(jsonify({'error': 'No payload received'}), 400)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO webhook_messages (payload, timestamp) VALUES (%s, %s) RETURNING id',
                    (psycopg2.extras.Json(payload), datetime.utcnow())
                )
                webhook_id = cur.fetchone()[0]
                conn.commit()
        
        print(f"webhook_id is {webhook_id}, payload is {payload}")

        # if I am in the message mention then:
        # if the message includes "hey @username" I reply "who calls my name music"
        # if the message includes "hey @username" I reply "its the voice of my mother"
        # if the message includes "someone is looking for you on the phone" If its not I don't aggrees "

        return make_response(jsonify({
            'status': 'success',
            'message': 'Webhook received and stored',
            'id': webhook_id
        }), 200)
        
    except Exception as e:
        return make_response(jsonify({
            'error': 'Failed to process webhook',
            'message': str(e)
        }), 500)

@app.route('/messages', methods=['GET'])
def get_messages() -> Response:

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
        return make_response(jsonify({
            'error': 'Failed to retrieve messages',
            'message': str(e)
        }), 500)

if __name__ == "__main__":

    app.run(debug=True, host=host, port=port)
