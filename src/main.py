from flask import Flask, request, Response, jsonify, make_response
import os
from dotenv import load_dotenv
from db import init_db, get_messages_from_db, store_message
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

        # TODO: add parsing of the message with pydantic latter..
        message_id = store_message(payload)
        
        print(f"message_id is {message_id}, payload is {payload}")

        # if I am in the message mention then:
        # if the message includes "hey @username" I reply "who calls my name music"
        # if the message includes "hey @username" I reply "its the voice of my mother"
        # if the message includes "someone is looking for you on the phone" If its not I don't aggrees "

        return make_response(jsonify({
            'status': 'success',
            'message': 'Webhook received and stored',
            'id': message_id
        }), 200)
        
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
