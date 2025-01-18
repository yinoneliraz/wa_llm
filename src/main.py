from flask import Flask, request, Response, jsonify, make_response
import os
from dotenv import load_dotenv
from db import init_db, get_messages_from_db
from webhook_logic import webhook_logic
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

        message_id = webhook_logic(payload)

        return make_response(jsonify({
            'status': 'success',
            'message': 'Webhook received and stored and handled',
            'id': message_id
        }), 200)
    except ValueError as validation_error:
        return make_response(jsonify({
            'error': 'Invalid message format',
            'details': str(validation_error)
        }), 400)
    except Exception as e:
        return make_response(jsonify({
            'error': 'Failed to process webhook',
            'message': str(e)
        }), 500)

@app.route('/messages', methods=['GET'])
def get_messages() -> Response:

    try:
        messages = get_messages_from_db()
        return jsonify(messages)
        
    except Exception as e:
        return make_response(jsonify({
            'error': 'Failed to retrieve messages',
            'message': str(e)
        }), 500)

if __name__ == "__main__":

    app.run(debug=True, host=host, port=port)
