"""
═══════════════════════════════════════════════════════════════════════════
    TELEGRAM UNIFIED SYSTEM - BACKEND WITH BUFFER VISIBILITY
    
    New Features:
    - Real-time buffer status API
    - Separate tracking of buffered vs sent messages
    - Message batching with 1-minute cycles
    - Anti-spam delays between groups
═══════════════════════════════════════════════════════════════════════════
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import time
import os
import threading
from collections import defaultdict

app = Flask(__name__, static_folder='static')
CORS(app)

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "8435296160:AAGERJ9ZGwlgR578OUcil84wrGLVrb8Ej7A")
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID', "8363089809")

# Database Configuration - Use absolute path
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
DATABASE_TYPE = os.environ.get('DATABASE_TYPE', 'sqlite')
DATABASE_URL = os.environ.get('DATABASE_URL', str(BASE_DIR / 'unified_system.db'))

# ═══════════════════════════════════════════════════════════════════════════
# 📋 PREDEFINED GROUPS WITH KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════

GROUPS = {
    'ZONE': {
        'name': 'Zone Signals',
        'group_id': os.environ.get('ZONE_GROUP_ID', '-1003668316027'),
        'keywords': ['ZONE'],
        'enabled': True
    },
    'INDEX': {
        'name': 'Index Option Buying',
        'group_id': os.environ.get('INDEX_GROUP_ID', '-5286555501'),
        'keywords': ['OPTION'],
        'enabled': True
    },
    'COMMODITY': {
        'name': 'Commodity',
        'group_id': os.environ.get('COMMODITY_GROUP_ID', '-5052531894'),
        'keywords': ['COMMODITY'],
        'enabled': True
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 🎯 MESSAGE BUFFER (In-Memory Storage)
# ═══════════════════════════════════════════════════════════════════════════

message_buffer = defaultdict(list)  # {group_id: [messages]}
buffer_lock = threading.Lock()
last_batch_time = datetime.now()

# ═══════════════════════════════════════════════════════════════════════════
# 💾 DATABASE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def _init_db_on_startup():
    """Initialize database tables when app starts"""
    try:
        from contextlib import contextmanager
        
        @contextmanager
        def get_connection():
            if DATABASE_TYPE == 'sqlite':
                import sqlite3
                conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
            elif DATABASE_TYPE == 'postgresql':
                import psycopg
                conn = psycopg.connect(DATABASE_URL)
            else:
                return
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            if DATABASE_TYPE == 'sqlite':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT,
                        group_id TEXT,
                        name TEXT,
                        invited_date TEXT,
                        expiry_date TEXT,
                        days_left INTEGER,
                        status TEXT,
                        PRIMARY KEY (user_id, group_id)
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        message TEXT,
                        group_id TEXT,
                        group_name TEXT,
                        matched_keywords TEXT,
                        status TEXT DEFAULT 'sent'
                    )
                ''')
            
            elif DATABASE_TYPE == 'postgresql':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(100),
                        group_id VARCHAR(100),
                        name VARCHAR(200),
                        invited_date VARCHAR(50),
                        expiry_date VARCHAR(50),
                        days_left INTEGER,
                        status VARCHAR(20),
                        PRIMARY KEY (user_id, group_id)
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id SERIAL PRIMARY KEY,
                        timestamp VARCHAR(50),
                        message TEXT,
                        group_id VARCHAR(100),
                        group_name VARCHAR(200),
                        matched_keywords VARCHAR(200),
                        status VARCHAR(20) DEFAULT 'sent'
                    )
                ''')
            
            conn.commit()
            print("✅ Database tables initialized successfully")
    except Exception as e:
        print(f"⚠️  Database initialization error: {e}")

_init_db_on_startup()

# ═══════════════════════════════════════════════════════════════════════════
# 💾 DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════════════════

def get_db_connection():
    """Get database connection based on DATABASE_TYPE"""
    if DATABASE_TYPE == 'sqlite':
        import sqlite3
        return sqlite3.connect(DATABASE_URL, check_same_thread=False)
    elif DATABASE_TYPE == 'postgresql':
        import psycopg
        return psycopg.connect(DATABASE_URL)
    else:
        raise ValueError(f"Unsupported database type: {DATABASE_TYPE}")

# ═══════════════════════════════════════════════════════════════════════════
# 📱 TELEGRAM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def send_to_telegram(group_id, text):
    """Send message to Telegram group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': group_id, 'text': text}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Failed to send to {group_id}: {e}")
        return False

def create_invite_link(group_id, expire_days=30):
    """Create invite link for group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
    expire_date = int(time.time()) + (expire_days * 86400)
    payload = {'chat_id': group_id, 'expire_date': expire_date, 'member_limit': 1}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['result']['invite_link'] if data.get('ok') else None
    except Exception as e:
        print(f"❌ Failed to create invite link: {e}")
        return None

def check_user_in_group(group_id, user_id):
    """Check if user is in group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
    try:
        response = requests.post(url, json={'chat_id': group_id, 'user_id': user_id}, timeout=10)
        data = response.json()
        if data.get('ok'):
            status = data['result']['status']
            return status in ['member', 'administrator', 'creator']
        return False
    except:
        return False

def ban_user_from_group(group_id, user_id):
    """Remove user from group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/banChatMember"
    try:
        response = requests.post(url, json={'chat_id': group_id, 'user_id': user_id}, timeout=10)
        response.raise_for_status()
        unban_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/unbanChatMember"
        requests.post(unban_url, json={'chat_id': group_id, 'user_id': user_id, 'only_if_banned': True})
        return True
    except Exception as e:
        print(f"❌ Failed to ban user: {e}")
        return False

def get_user_info(user_id):
    """Get user info from Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChat"
    try:
        response = requests.post(url, json={'chat_id': user_id}, timeout=10)
        data = response.json()
        if data.get('ok'):
            user = data['result']
            username = user.get('username', '')
            if username:
                return f"@{username}"
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
            return f"{first_name} {last_name}".strip() or "Unknown"
        return "Unknown"
    except:
        return "Unknown"

def get_group_admins(group_id):
    """Get all admins from Telegram group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatAdministrators"
    try:
        response = requests.get(url, params={'chat_id': group_id}, timeout=10)
        result = response.json()
        admins = []
        if result.get('ok'):
            for admin in result.get('result', []):
                user = admin.get('user', {})
                admins.append({
                    'user_id': str(user.get('id')),
                    'first_name': user.get('first_name', 'Unknown'),
                    'username': user.get('username', ''),
                    'is_bot': user.get('is_bot', False),
                    'status': admin.get('status', 'member')
                })
        return admins
    except Exception as e:
        print(f"❌ Failed to get admins: {e}")
        return []

# ═══════════════════════════════════════════════════════════════════════════
# 🗃️ DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def add_user(group_id, user_id, days):
    """Add user to group"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    name = get_user_info(user_id)
    invited_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    
    if DATABASE_TYPE == 'sqlite':
        cursor.execute(f'''
            INSERT OR REPLACE INTO users 
            (user_id, group_id, name, invited_date, expiry_date, days_left, status)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'active')
        ''', (user_id, group_id, name, invited_date, expiry_date, days))
    elif DATABASE_TYPE == 'postgresql':
        cursor.execute('''
            INSERT INTO users 
            (user_id, group_id, name, invited_date, expiry_date, days_left, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'active')
            ON CONFLICT (user_id, group_id) DO UPDATE SET
            name=EXCLUDED.name, invited_date=EXCLUDED.invited_date, 
            expiry_date=EXCLUDED.expiry_date, days_left=EXCLUDED.days_left, status='active'
        ''', (user_id, group_id, name, invited_date, expiry_date, days))
    
    conn.commit()
    conn.close()

def get_users_by_group(group_id):
    """Get all users for a specific group"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
        cursor.execute(f'''
            SELECT user_id, name, invited_date, expiry_date, days_left, status
            FROM users WHERE group_id = {placeholder} ORDER BY invited_date DESC
        ''', (group_id,))
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        print(f"⚠️ Database error in get_users_by_group: {e}")
        return []

def update_user_expiry(group_id, user_id, additional_days):
    """Extend user expiry"""
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT expiry_date FROM users WHERE group_id = {placeholder} AND user_id = {placeholder}
    ''', (group_id, user_id))
    result = cursor.fetchone()
    if result:
        current_expiry = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        new_expiry = current_expiry + timedelta(days=additional_days)
        cursor.execute(f'''
            UPDATE users SET expiry_date = {placeholder}, days_left = days_left + {placeholder}
            WHERE group_id = {placeholder} AND user_id = {placeholder}
        ''', (new_expiry.strftime('%Y-%m-%d %H:%M:%S'), additional_days, group_id, user_id))
        conn.commit()
    conn.close()

def remove_user(group_id, user_id):
    """Remove user from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'DELETE FROM users WHERE group_id = {placeholder} AND user_id = {placeholder}', (group_id, user_id))
    conn.commit()
    conn.close()

def log_message(message, group_id, group_name, matched_keywords):
    """Log message sent to group"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
        cursor.execute(f'''
            INSERT INTO messages (timestamp, message, group_id, group_name, matched_keywords, status)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'sent')
        ''', (timestamp, message, group_id, group_name, matched_keywords))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Database error in log_message: {e}")

def get_messages_by_group(group_id, limit=50):
    """Get messages for specific group"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
        cursor.execute(f'''
            SELECT timestamp, message, matched_keywords, status
            FROM messages WHERE group_id = {placeholder} ORDER BY id DESC LIMIT {placeholder}
        ''', (group_id, limit))
        messages = cursor.fetchall()
        conn.close()
        return messages
    except Exception as e:
        print(f"⚠️ Database error in get_messages_by_group: {e}")
        return []

def get_all_messages(limit=100):
    """Get all messages across all groups"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
        cursor.execute(f'''
            SELECT timestamp, message, group_name, matched_keywords, status
            FROM messages ORDER BY id DESC LIMIT {placeholder}
        ''', (limit,))
        messages = cursor.fetchall()
        conn.close()
        return messages
    except Exception as e:
        print(f"⚠️ Database error in get_all_messages: {e}")
        return []

def get_stats():
    """Get statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM users')
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
        active_users = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"⚠️ Database error in get_stats: {e}")
        total_users = 0
        active_users = 0
        total_messages = 0
    
    enabled_groups = sum(1 for g in GROUPS.values() if g['enabled'])
    
    # Add buffer stats
    with buffer_lock:
        buffered_count = sum(len(msgs) for msgs in message_buffer.values())
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'total_messages': total_messages,
        'enabled_groups': enabled_groups,
        'buffered_messages': buffered_count
    }

# ═══════════════════════════════════════════════════════════════════════════
# 🎯 MESSAGE BUFFERING & BATCHING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

def add_to_buffer(group_id, group_name, message, keyword):
    """Add message to buffer"""
    with buffer_lock:
        message_buffer[group_id].append({
            'message': message,
            'group_name': group_name,
            'keyword': keyword,
            'received_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    print(f"📥 Buffered for {group_name}: {len(message_buffer[group_id])} messages")

def process_buffer():
    """Process buffered messages every minute"""
    global last_batch_time
    
    while True:
        time.sleep(60)  # Wait 1 minute
        
        # Take a snapshot of the buffer and clear it immediately
        buffer_snapshot = {}
        with buffer_lock:
            if not message_buffer:
                continue
            
            # Copy buffer and clear it
            for group_id, messages in message_buffer.items():
                if messages:
                    buffer_snapshot[group_id] = messages.copy()
            
            # Clear the buffer immediately
            message_buffer.clear()
        
        if not buffer_snapshot:
            continue
        
        print("\n" + "═" * 70)
        print("⏰ PROCESSING BUFFER (1-minute cycle)")
        print("═" * 70)
        
        groups_to_send = list(buffer_snapshot.keys())
        
        for idx, group_id in enumerate(groups_to_send):
            messages = buffer_snapshot[group_id]
            
            if not messages:
                continue
            
            # Combine all messages for this group with 3 line breaks between them
            combined_message = "\n\n\n".join([msg['message'] for msg in messages])
            group_name = messages[0]['group_name']
            keywords = ", ".join(set([msg['keyword'] for msg in messages]))
            
            print(f"\n📤 Sending to {group_name}: {len(messages)} alerts combined")
            
            # Send to Telegram
            if send_to_telegram(group_id, combined_message):
                # Log only after successful send
                log_message(combined_message, group_id, group_name, keywords)
                print(f"✅ Sent successfully to {group_name}")
            else:
                print(f"❌ Send failed to {group_name}")
            
            # Add 10-second delay between groups (if multiple groups)
            if idx < len(groups_to_send) - 1:
                print("⏳ Waiting 10 seconds before next group...")
                time.sleep(10)
        
        print(f"✅ Batch complete! Sent to {len(groups_to_send)} group(s)")
        print("═" * 70 + "\n")
        last_batch_time = datetime.now()

# Start buffer processing thread
buffer_thread = threading.Thread(target=process_buffer, daemon=True)
buffer_thread.start()

# ═══════════════════════════════════════════════════════════════════════════
# 🎯 MESSAGE ROUTING
# ═══════════════════════════════════════════════════════════════════════════

def route_message(message):
    """Route message to buffer based on keywords"""
    message_upper = message.upper()
    routed_to = []
    
    for group_key, group_config in GROUPS.items():
        if not group_config['enabled']:
            continue
        
        for keyword in group_config['keywords']:
            if keyword.upper() in message_upper:
                group_id = group_config['group_id']
                group_name = group_config['name']
                
                add_to_buffer(group_id, group_name, message, keyword)
                routed_to.append({'group_name': group_name, 'keyword': keyword})
                break
    
    return routed_to

# ═══════════════════════════════════════════════════════════════════════════
# 🌐 API ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return send_from_directory('static', 'index.html')

@app.route('/webhook/router', methods=['POST'])
def webhook_router():
    """Main webhook - receives TradingView alerts"""
    try:
        raw_data = request.data.decode('utf-8')
        if not raw_data:
            return jsonify({'error': 'No data received'}), 400
        
        print("\n🔔 ALERT RECEIVED:", raw_data)
        routed_to = route_message(raw_data)
        
        if routed_to:
            return jsonify({
                'success': True,
                'buffered_for_groups': len(routed_to),
                'groups': [item['group_name'] for item in routed_to]
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No matching groups'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/buffer', methods=['GET'])
def api_buffer_status():
    """Get current buffer status"""
    with buffer_lock:
        buffer_status = []
        for group_id, messages in message_buffer.items():
            group_name = next((g['name'] for g in GROUPS.values() if g['group_id'] == group_id), 'Unknown')
            buffer_status.append({
                'group_id': group_id,
                'group_name': group_name,
                'count': len(messages),
                'messages': messages
            })
    
    time_since_last = (datetime.now() - last_batch_time).seconds
    next_send_in = max(0, 60 - time_since_last)
    
    return jsonify({
        'buffer': buffer_status,
        'next_send_in_seconds': next_send_in,
        'last_batch': last_batch_time.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@app.route('/api/config', methods=['GET'])
def api_config():
    return jsonify({'admin_id': ADMIN_USER_ID, 'database_type': DATABASE_TYPE}), 200

@app.route('/api/stats', methods=['GET'])
def api_stats():
    return jsonify(get_stats()), 200

@app.route('/api/groups', methods=['GET'])
def api_groups():
    groups_list = []
    for key, config in GROUPS.items():
        groups_list.append({
            'key': key,
            'name': config['name'],
            'group_id': config['group_id'],
            'keywords': config['keywords'],
            'enabled': config['enabled']
        })
    return jsonify({'groups': groups_list}), 200

@app.route('/api/group/<group_id>/users', methods=['GET'])
def api_group_users(group_id):
    users = get_users_by_group(group_id)
    result = []
    for user_id, name, invited, expiry, days, status in users:
        joined = check_user_in_group(group_id, user_id)
        result.append({
            'user_id': user_id, 'name': name, 'invited_date': invited,
            'expiry_date': expiry, 'days_left': days, 'status': status, 'joined': joined
        })
    return jsonify({'users': result}), 200

@app.route('/api/group/<group_id>/admins', methods=['GET'])
def api_group_admins(group_id):
    admins = get_group_admins(group_id)
    return jsonify({'admins': admins, 'count': len(admins)}), 200

@app.route('/api/group/<group_id>/messages', methods=['GET'])
def api_group_messages(group_id):
    limit = request.args.get('limit', 50, type=int)
    messages = get_messages_by_group(group_id, limit)
    result = []
    for timestamp, message, keywords, status in messages:
        result.append({'timestamp': timestamp, 'message': message, 'keywords': keywords, 'status': status})
    return jsonify({'messages': result}), 200

@app.route('/api/messages', methods=['GET'])
def api_all_messages():
    limit = request.args.get('limit', 100, type=int)
    messages = get_all_messages(limit)
    result = []
    for timestamp, message, group_name, keywords, status in messages:
        result.append({'timestamp': timestamp, 'message': message, 'group_name': group_name, 'keywords': keywords, 'status': status})
    return jsonify({'messages': result}), 200

@app.route('/api/user/add', methods=['POST'])
def api_add_user():
    data = request.json
    if data.get('admin_id') != ADMIN_USER_ID:
        return jsonify({'error': 'Unauthorized'}), 403
    
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    days = int(data.get('days', 30))
    
    invite_link = create_invite_link(group_id, days)
    if not invite_link:
        return jsonify({'error': 'Failed to create invite link'}), 500
    
    add_user(group_id, user_id, days)
    message = f"🎉 You've been invited!\n\nValid for: {days} days\nJoin now: {invite_link}"
    send_to_telegram(user_id, message)
    return jsonify({'success': True, 'invite_link': invite_link}), 200

@app.route('/api/user/extend', methods=['POST'])
def api_extend_user():
    data = request.json
    if data.get('admin_id') != ADMIN_USER_ID:
        return jsonify({'error': 'Unauthorized'}), 403
    update_user_expiry(data.get('group_id'), data.get('user_id'), int(data.get('days', 30)))
    return jsonify({'success': True}), 200

@app.route('/api/user/remove', methods=['POST'])
def api_remove_user():
    data = request.json
    if data.get('admin_id') != ADMIN_USER_ID:
        return jsonify({'error': 'Unauthorized'}), 403
    ban_user_from_group(data.get('group_id'), data.get('user_id'))
    remove_user(data.get('group_id'), data.get('user_id'))
    return jsonify({'success': True}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'database': DATABASE_TYPE}), 200

if __name__ == '__main__':
    print("\n" + "═" * 70)
    print("║" + " " * 18 + "TELEGRAM UNIFIED SYSTEM" + " " * 29 + "║")
    print("═" * 70)
    print("✅ Buffer processing started (1-minute cycles)")
    print(f"✅ Bot Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print(f"✅ Database: {DATABASE_TYPE}")
    print("\n📋 CONFIGURED GROUPS:")
    for key, config in GROUPS.items():
        status = "✅ ACTIVE" if config['enabled'] else "⏸️  DISABLED"
        print(f"   {status} {config['name']}")
        print(f"      Group ID: {config['group_id']}")
        print(f"      Keywords: {', '.join(config['keywords'])}")
    print("\n🌐 Server starting...")
    print("📡 Webhook: /webhook/router")
    print("🏠 Dashboard: /")
    print("═" * 70 + "\n")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 
