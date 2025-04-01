from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import uuid
from datetime import datetime
import secrets
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Create static folder if it doesn't exist
if not os.path.exists('static'):
    os.makedirs('static')

# Store messages in memory (in production, you would use a database)
messages = []

# Store user data
users = {}

# Store public keys for users
public_keys = {}

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['username'] = f"User_{session['user_id'][:5]}"
        users[session['user_id']] = session['username']
    return render_template('index.html', username=session.get('username'))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/set_username', methods=['POST'])
def set_username():
    data = request.get_json()
    if 'username' in data and data['username'].strip():
        old_username = session.get('username')
        new_username = data['username'].strip()
        session['username'] = new_username
        
        # Update username in users dictionary
        user_id = session.get('user_id')
        if user_id:
            users[user_id] = new_username
            
            # Update username in existing messages
            for message in messages:
                if message['user_id'] == user_id:
                    message['username'] = new_username
            
            # Emit updated message list to all clients
            socketio.emit('message_history', messages)
            
            return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/get_current_user', methods=['GET'])
def get_current_user():
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })

@app.route('/register_public_key', methods=['POST'])
def register_public_key():
    data = request.get_json()
    user_id = session.get('user_id')
    
    if user_id and 'publicKey' in data:
        public_keys[user_id] = data['publicKey']
        # Notify all users about the new public key
        socketio.emit('user_public_key', {
            'user_id': user_id,
            'publicKey': data['publicKey']
        })
        return jsonify({'success': True})
    
    return jsonify({'success': False})

@app.route('/get_public_keys', methods=['GET'])
def get_public_keys():
    return jsonify(public_keys)

# Socket events
@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if user_id:
        # Join a room specific to this user
        join_room(user_id)
        
    # Send message history to newly connected users
    emit('message_history', messages)
    
    # Send current user info
    emit('current_user', {
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })
    
    # Send all public keys to the newly connected user
    emit('all_public_keys', public_keys)
    
    # Notify all users about this user's connection
    user_id = session.get('user_id')
    if user_id:
        socketio.emit('user_connected', {
            'user_id': user_id,
            'username': users.get(user_id, f"User_{user_id[:5]}")
        })

@socketio.on('send_message')
def handle_message(data):
    user_id = session.get('user_id', str(uuid.uuid4()))
    username = session.get('username', f"User_{user_id[:5]}")
    
    # Create message object
    message = {
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'username': username,
        'encrypted': True,
        'recipients': data.get('recipients', {}),  # Dictionary of user_id -> encrypted message
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'replyTo': data.get('replyTo', None)
    }
    
    # Add to message history
    messages.append(message)
    
    # Broadcast to all connected clients
    socketio.emit('new_message', message)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = session.get('user_id')
    if user_id:
        socketio.emit('user_disconnected', {
            'user_id': user_id,
            'username': users.get(user_id, f"User_{user_id[:5]}")
        })

if __name__ == '__main__':
    socketio.run(app, debug=True)