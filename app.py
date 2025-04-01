from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
import uuid
from datetime import datetime
import secrets
import os
import sqlite3
import hashlib
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Create database directory if it doesn't exist
if not os.path.exists('data'):
    os.makedirs('data')

# Database setup
DATABASE = 'data/chat.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create messages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        username TEXT NOT NULL,
        encrypted BOOLEAN NOT NULL,
        content TEXT,
        timestamp TEXT NOT NULL,
        reply_to TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create message_recipients table for encrypted messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS message_recipients (
        message_id TEXT NOT NULL,
        recipient_id TEXT NOT NULL,
        encrypted_content TEXT NOT NULL,
        PRIMARY KEY (message_id, recipient_id),
        FOREIGN KEY (message_id) REFERENCES messages (id),
        FOREIGN KEY (recipient_id) REFERENCES users (id)
    )
    ''')
    
    # Create public_keys table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS public_keys (
        user_id TEXT PRIMARY KEY,
        public_key TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize the database
init_db()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    return stored_hash == hash_password(password)

def username_exists(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM users WHERE username = ?', (username,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(username, password):
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)',
        (user_id, username, password_hash)
    )
    conn.commit()
    conn.close()
    return user_id

def save_message(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert into messages table
    cursor.execute(
        'INSERT INTO messages (id, user_id, username, encrypted, content, timestamp, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (
            message['id'],
            message['user_id'],
            message['username'],
            message['encrypted'],
            message.get('text', None),  # For non-encrypted messages
            message['timestamp'],
            message.get('replyTo', None)
        )
    )
    
    # If encrypted, store recipient-specific encrypted content
    if message['encrypted'] and 'recipients' in message:
        for recipient_id, encrypted_content in message['recipients'].items():
            cursor.execute(
                'INSERT INTO message_recipients (message_id, recipient_id, encrypted_content) VALUES (?, ?, ?)',
                (message['id'], recipient_id, encrypted_content)
            )
    
    conn.commit()
    conn.close()

def load_messages():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all messages
    cursor.execute('''
    SELECT * FROM messages 
    ORDER BY timestamp ASC
    ''')
    
    messages_data = cursor.fetchall()
    messages = []
    
    for msg in messages_data:
        msg_dict = dict(msg)
        
        # If encrypted, get all recipients
        if msg_dict['encrypted']:
            cursor.execute(
                'SELECT recipient_id, encrypted_content FROM message_recipients WHERE message_id = ?',
                (msg_dict['id'],)
            )
            recipients_data = cursor.fetchall()
            
            recipients = {}
            for rec in recipients_data:
                recipients[rec['recipient_id']] = rec['encrypted_content']
            
            msg_dict['recipients'] = recipients
        
        messages.append(msg_dict)
    
    conn.close()
    return messages

def save_public_key(user_id, public_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if key exists for this user
    cursor.execute('SELECT 1 FROM public_keys WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone() is not None
    
    if exists:
        cursor.execute(
            'UPDATE public_keys SET public_key = ? WHERE user_id = ?',
            (public_key, user_id)
        )
    else:
        cursor.execute(
            'INSERT INTO public_keys (user_id, public_key) VALUES (?, ?)',
            (user_id, public_key)
        )
    
    conn.commit()
    conn.close()

def load_public_keys():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, public_key FROM public_keys')
    keys = {row['user_id']: row['public_key'] for row in cursor.fetchall()}
    conn.close()
    return keys

# Load initial data
messages = load_messages()
public_keys = load_public_keys()

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('chat'))
        return render_template('login.html')
    
    # Handle POST request (AJAX)
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'missing_fields'})
    
    user = get_user_by_username(username)
    
    if not user:
        return jsonify({'success': False, 'error': 'user_not_found'})
    
    if not verify_password(user['password_hash'], password):
        return jsonify({'success': False, 'error': 'invalid_password'})
    
    # Set session
    session['user_id'] = user['id']
    session['username'] = user['username']
    
    return jsonify({'success': True})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('chat'))
        return render_template('register.html')
    
    # Handle POST request (AJAX)
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'missing_fields'})
    
    # Validate username
    if len(username) < 3 or not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({'success': False, 'error': 'invalid_username'})
    
    # Validate password
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'invalid_password'})
    
    # Check if username exists
    if username_exists(username):
        return jsonify({'success': False, 'error': 'username_taken'})
    
    # Create user
    user_id = create_user(username, password)
    
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/set_username', methods=['POST'])
def set_username():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not_authenticated'})
    
    data = request.get_json()
    if 'username' in data and data['username'].strip():
        new_username = data['username'].strip()
        
        # Check if username is taken (by someone else)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                      (new_username, session['user_id']))
        exists = cursor.fetchone() is not None
        conn.close()
        
        if exists:
            return jsonify({'success': False, 'error': 'username_taken'})
        
        # Update username in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET username = ? WHERE id = ?', 
                     (new_username, session['user_id']))
        
        # Update username in messages
        cursor.execute('UPDATE messages SET username = ? WHERE user_id = ?', 
                     (new_username, session['user_id']))
        
        conn.commit()
        conn.close()
        
        # Update session
        session['username'] = new_username
        
        # Update messages in memory
        for message in messages:
            if message['user_id'] == session['user_id']:
                message['username'] = new_username
        
        # Emit updated message list to all clients
        socketio.emit('message_history', messages)
        
        return jsonify({'success': True})
    
    return jsonify({'success': False})

@app.route('/get_current_user', methods=['GET'])
def get_current_user():
    if 'user_id' not in session:
        return jsonify({'error': 'not_authenticated'})
    
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })

@app.route('/register_public_key', methods=['POST'])
def register_public_key():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'not_authenticated'})
    
    data = request.get_json()
    user_id = session.get('user_id')
    
    if user_id and 'publicKey' in data:
        public_keys[user_id] = data['publicKey']
        save_public_key(user_id, data['publicKey'])
        
        # Notify all users about the new public key
        socketio.emit('user_public_key', {
            'user_id': user_id,
            'publicKey': data['publicKey']
        })
        return jsonify({'success': True})
    
    return jsonify({'success': False})

@app.route('/get_public_keys', methods=['GET'])
def get_public_keys():
    if 'user_id' not in session:
        return jsonify({'error': 'not_authenticated'})
    
    return jsonify(public_keys)

# Socket events
@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        return  # Prevent connection if not authenticated
    
    user_id = session.get('user_id')
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
    socketio.emit('user_connected', {
        'user_id': user_id,
        'username': session.get('username')
    })

@socketio.on('send_message')
def handle_message(data):
    if 'user_id' not in session:
        return  # Prevent sending if not authenticated
    
    user_id = session.get('user_id')
    username = session.get('username')
    
    # Create message object
    message = {
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'username': username,
        'encrypted': True,
        'recipients': data.get('recipients', {}),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'replyTo': data.get('replyTo', None)
    }
    
    # Add to message history
    messages.append(message)
    
    # Save to database
    save_message(message)
    
    # Broadcast to all connected clients
    socketio.emit('new_message', message)

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        socketio.emit('user_disconnected', {
            'user_id': session.get('user_id'),
            'username': session.get('username')
        })

if __name__ == '__main__':
    socketio.run(app, debug=True)