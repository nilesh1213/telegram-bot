"""
═══════════════════════════════════════════════════════════════════════════
    TELEGRAM UNIFIED SYSTEM - COMPLETE VERSION
    
    Features:
    ✅ 60-second MESSAGE BUFFER system
    ✅ User management (add/extend/remove)
    ✅ Multi-database support (SQLite for local, PostgreSQL for production)
    ✅ Real-time dashboard
    
    For LOCAL testing:
    - Uses SQLite database (no setup needed)
    - Just run: python app.py
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

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "8114249780:AAHxXXmK68vnI7-QpO1HEsTQv4w2cKPqQ-A")
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID', "8363089809")

# Database Configuration - Check environment variable first
# Set USE_LOCAL_SQLITE=False in production (Render/Railway)
# Set USE_LOCAL_SQLITE=True for local development
USE_LOCAL_SQLITE = os.environ.get('USE_LOCAL_SQLITE', 'True').lower() == 'true'

if USE_LOCAL_SQLITE:
    DATABASE_TYPE = 'sqlite'
    DATABASE_URL = 'unified_system.db'
    print("🔧 Using LOCAL SQLite database")
else:
    DATABASE_TYPE = os.environ.get('DATABASE_TYPE', 'postgresql')
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL not set, falling back to SQLite")
        DATABASE_TYPE = 'sqlite'
        DATABASE_URL = 'unified_system.db'
    else:
        # If PostgreSQL URL provided, auto-detect
        if 'postgres://' in DATABASE_URL or 'postgresql://' in DATABASE_URL:
            DATABASE_TYPE = 'postgresql'
            if DATABASE_URL.startswith('postgres://'):
                DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        print(f"🔧 Using {DATABASE_TYPE.upper()} database from environment")

# ═══════════════════════════════════════════════════════════════════════════
# 📋 GROUPS CONFIGURATION
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
    },
    'CRUDE': {
        'name': 'Crude 👉',
        'group_id': os.environ.get('CRUDE_GROUP_ID', '-1003827512738'),
        'keywords': ['CRUDE'],
        'enabled': True
    },
    'NATURALGAS': {
        'name': 'Natural Gas 👉',
        'group_id': os.environ.get('NATURALGAS_GROUP_ID', '-1003495490379'),
        'keywords': ['NATURALGAS'],
        'enabled': True
    },
    'SILVER': {
        'name': 'Silver 👉',
        'group_id': os.environ.get('SILVER_GROUP_ID', '-1003479189825'),
        'keywords': ['SILVER'],
        'enabled': True
    },
    'GOLD': {
        'name': 'Gold 👉',
        'group_id': os.environ.get('GOLD_GROUP_ID', '-1003668837632'),
        'keywords': ['GOLD'],
        'enabled': True
    },
    'COPPER': {
        'name': 'Copper 👉',
        'group_id': os.environ.get('COPPER_GROUP_ID', '-1003832712767'),
        'keywords': ['COPPER'],
        'enabled': True
    },
    'CASH': {
        'name': 'Cash Intraday 👉',
        'group_id': os.environ.get('CASH_GROUP_ID', '-1003603299587'),  # CORRECTED
        'keywords': ['CASH'],
        'enabled': True
    },
    'SWING': {
        'name': 'Swing and Investment Cash 👉',
        'group_id': os.environ.get('SWING_GROUP_ID', '-1003563158525'),  # CORRECTED
        'keywords': ['SWING'],
        'enabled': True
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# ⏳ BUFFER SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

message_buffer = defaultdict(list)
buffer_lock = threading.Lock()
last_batch_time = datetime.now()

def add_to_buffer(group_id, group_name, message, keyword):
    """Add message to buffer for batching"""
    with buffer_lock:
        message_buffer[group_id].append({
            'message': message,
            'group_name': group_name,
            'keyword': keyword,
            'received_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        print(f"📥 Added to buffer: {group_name} (Total: {len(message_buffer[group_id])})")

def process_buffer():
    """Background thread - sends buffered messages every 60 seconds"""
    global last_batch_time
    print("🔄 Buffer thread starting...")
    
    while True:
        try:
            time.sleep(60)  # Wait 60 seconds
            print("⏰ Buffer cycle - checking for messages...")
            
            # Take snapshot of buffer and clear it
            buffer_snapshot = {}
            with buffer_lock:
                if message_buffer:
                    for gid, msgs in message_buffer.items():
                        if msgs:
                            buffer_snapshot[gid] = msgs.copy()
                    message_buffer.clear()
            
            # Send buffered messages
            if buffer_snapshot:
                print(f"📤 Sending {len(buffer_snapshot)} group(s)")
                
                for idx, (gid, msgs) in enumerate(buffer_snapshot.items()):
                    # Combine all messages for this group
                    combined = "\n\n\n".join([m['message'] for m in msgs])
                    
                    if send_to_telegram(gid, combined):
                        # Log the combined message
                        log_message(combined, gid, msgs[0]['group_name'], 
                                  ", ".join(set([m['keyword'] for m in msgs])))
                        print(f"✅ Sent to {msgs[0]['group_name']} ({len(msgs)} messages)")
                    
                    # Delay between groups to avoid rate limits
                    if idx < len(buffer_snapshot) - 1:
                        time.sleep(5)  # 5 seconds between groups
                
                last_batch_time = datetime.now()
            else:
                print("📭 No messages in buffer")
                
        except Exception as e:
            print(f"❌ Buffer error: {e}")

# Start buffer thread
buffer_thread = threading.Thread(target=process_buffer, daemon=True)
buffer_thread.start()
print("✅ Buffer thread started")

# ═══════════════════════════════════════════════════════════════════════════
# 💾 DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════════════════

def get_db_connection():
    """Get database connection based on DATABASE_TYPE"""
    if DATABASE_TYPE == 'sqlite':
        import sqlite3
        conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    elif DATABASE_TYPE == 'postgresql':
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        raise ValueError(f"Unsupported database type: {DATABASE_TYPE}")

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_TYPE == 'sqlite':
        # Users table
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
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                message TEXT,
                group_id TEXT,
                group_name TEXT,
                matched_keywords TEXT
            )
        ''')
    
    elif DATABASE_TYPE == 'postgresql':
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(100),
                group_id VARCHAR(100),
                name VARCHAR(200),
                invited_date TIMESTAMP,
                expiry_date TIMESTAMP,
                days_left INTEGER,
                status VARCHAR(20),
                PRIMARY KEY (user_id, group_id)
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP,
                message TEXT,
                group_id VARCHAR(100),
                group_name VARCHAR(200),
                matched_keywords VARCHAR(200)
            )
        ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

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
        # Show detailed error response from Telegram
        try:
            error_details = response.json()
            print(f"   Telegram API Response: {error_details}")
        except:
            pass
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
        
        if data.get('ok'):
            return data['result']['invite_link']
        return None
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
        
        # Unban so they can be re-invited later
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
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
            username = user.get('username', '')
            
            if username:
                return f"@{username}"
            elif first_name or last_name:
                return f"{first_name} {last_name}".strip()
            else:
                return "Unknown"
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
    invited_date = datetime.now()
    expiry_date = datetime.now() + timedelta(days=days)
    
    if DATABASE_TYPE == 'sqlite':
        invited_date_str = invited_date.strftime('%Y-%m-%d %H:%M:%S')
        expiry_date_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, group_id, name, invited_date, expiry_date, days_left, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        ''', (user_id, group_id, name, invited_date_str, expiry_date_str, days))
        
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT user_id, name, invited_date, expiry_date, days_left, status
        FROM users
        WHERE group_id = {placeholder}
        ORDER BY invited_date DESC
    ''', (group_id,))
    
    users = cursor.fetchall()
    conn.close()
    return users

def update_user_expiry(group_id, user_id, additional_days):
    """Extend user expiry"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT expiry_date FROM users
        WHERE group_id = {placeholder} AND user_id = {placeholder}
    ''', (group_id, user_id))
    
    result = cursor.fetchone()
    if result:
        if DATABASE_TYPE == 'sqlite':
            current_expiry = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            new_expiry = current_expiry + timedelta(days=additional_days)
            new_expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        else:  # postgresql
            current_expiry = result[0]
            # Remove timezone for comparison if present
            if hasattr(current_expiry, 'tzinfo') and current_expiry.tzinfo is not None:
                current_expiry = current_expiry.replace(tzinfo=None)
            new_expiry = current_expiry + timedelta(days=additional_days)
            new_expiry_str = new_expiry
        
        cursor.execute(f'''
            UPDATE users
            SET expiry_date = {placeholder}
            WHERE group_id = {placeholder} AND user_id = {placeholder}
        ''', (new_expiry_str, group_id, user_id))
        
        conn.commit()
    
    conn.close()

def reduce_user_expiry(group_id, user_id, reduce_days):
    """Reduce user expiry (but not below current date) - Returns error if would go negative"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT expiry_date FROM users
        WHERE group_id = {placeholder} AND user_id = {placeholder}
    ''', (group_id, user_id))
    
    result = cursor.fetchone()
    if result:
        if DATABASE_TYPE == 'sqlite':
            current_expiry = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        else:  # postgresql
            current_expiry = result[0]
            # Remove timezone for comparison if present
            if current_expiry.tzinfo is not None:
                current_expiry = current_expiry.replace(tzinfo=None)
        
        # Calculate what the new expiry would be
        new_expiry = current_expiry - timedelta(days=reduce_days)
        current_time = datetime.now()
        
        # Check if reduction would result in negative days
        if new_expiry < current_time:
            # Calculate how many days they currently have left
            days_left = max(0, (current_expiry - current_time).days)
            conn.close()
            return {'error': f'Cannot reduce by {reduce_days} days. User only has {days_left} days left. Maximum you can reduce is {days_left} days.'}
        
        # Safe to reduce
        if DATABASE_TYPE == 'sqlite':
            new_expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        else:
            new_expiry_str = new_expiry
        
        cursor.execute(f'''
            UPDATE users
            SET expiry_date = {placeholder}
            WHERE group_id = {placeholder} AND user_id = {placeholder}
        ''', (new_expiry_str, group_id, user_id))
        
        conn.commit()
        conn.close()
        return {'success': True}
    
    conn.close()
    return {'error': 'User not found'}

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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now()
    
    if DATABASE_TYPE == 'sqlite':
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO messages (timestamp, message, group_id, group_name, matched_keywords)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp_str, message, group_id, group_name, matched_keywords))
    elif DATABASE_TYPE == 'postgresql':
        cursor.execute('''
            INSERT INTO messages (timestamp, message, group_id, group_name, matched_keywords)
            VALUES (%s, %s, %s, %s, %s)
        ''', (timestamp, message, group_id, group_name, matched_keywords))
    
    conn.commit()
    conn.close()

def get_messages_by_group(group_id, limit=50):
    """Get messages for specific group"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT timestamp, message, matched_keywords
        FROM messages
        WHERE group_id = {placeholder}
        ORDER BY id DESC
        LIMIT {placeholder}
    ''', (group_id, limit))
    
    messages = cursor.fetchall()
    conn.close()
    return messages

def get_all_messages(limit=100):
    """Get all messages across all groups"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT timestamp, message, group_name, matched_keywords
        FROM messages
        ORDER BY id DESC
        LIMIT {placeholder}
    ''', (limit,))
    
    messages = cursor.fetchall()
    conn.close()
    return messages

def get_stats():
    """Get statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
    active_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_messages = cursor.fetchone()[0]
    
    enabled_groups = sum(1 for g in GROUPS.values() if g['enabled'])
    
    conn.close()
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'total_messages': total_messages,
        'enabled_groups': enabled_groups
    }

# ═══════════════════════════════════════════════════════════════════════════
# 🌐 API ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """Serve frontend HTML"""
    return send_from_directory('static', 'index.html')

@app.route('/webhook/router', methods=['POST'])
def webhook_router():
    """Main webhook - receives TradingView alerts and adds to buffer"""
    try:
        # Get raw data
        content_type = request.headers.get('Content-Type', '')
        
        # Handle JSON format (TradingView default)
        if 'application/json' in content_type:
            data = request.get_json()
            if data and isinstance(data, dict):
                # Try different possible keys TradingView might use
                raw_data = data.get('message') or data.get('text') or data.get('alert') or data.get('data') or str(data)
            else:
                raw_data = request.data.decode('utf-8')
        else:
            # Handle plain text format (manual tests)
            raw_data = request.data.decode('utf-8')
        
        if not raw_data:
            print("❌ ERROR: No data received!", flush=True)
            return jsonify({'error': 'No data received'}), 400
        
        print("\n" + "═" * 70, flush=True)
        print("🔔 ALERT RECEIVED - ADDING TO BUFFER", flush=True)
        print("═" * 70, flush=True)
        print(f"Content-Type: {content_type}", flush=True)
        print(f"Raw Request Data: {request.data[:200]}", flush=True)
        print(f"Processed Message: {raw_data}", flush=True)
        print("─" * 70, flush=True)
        
        # Route to appropriate groups based on keywords
        message_upper = str(raw_data).upper()
        routed_to = []
        
        print(f"🔍 Searching for keywords in: {message_upper[:100]}", flush=True)
        
        for group_key, group_config in GROUPS.items():
            if not group_config['enabled']:
                print(f"⏸️  Skipping disabled group: {group_config['name']}", flush=True)
                continue
            
            for keyword in group_config['keywords']:
                print(f"   Checking keyword '{keyword}' in message...", flush=True)
                if keyword.upper() in message_upper:
                    group_id = group_config['group_id']
                    group_name = group_config['name']
                    
                    print(f"   ✅ MATCH! Keyword '{keyword}' found!", flush=True)
                    
                    # Add to buffer instead of sending immediately
                    add_to_buffer(group_id, group_name, str(raw_data), keyword)
                    routed_to.append({'group_name': group_name})
                    
                    break
                else:
                    print(f"   ❌ No match for '{keyword}'", flush=True)
        
        if routed_to:
            print(f"✅ Added to {len(routed_to)} buffer(s)", flush=True)
            for item in routed_to:
                print(f"   → {item['group_name']}", flush=True)
            print("═" * 70 + "\n", flush=True)
            
            return jsonify({
                'success': True,
                'buffered_in_groups': len(routed_to),
                'groups': [item['group_name'] for item in routed_to]
            }), 200
        else:
            print("⚠️  NO GROUPS MATCHED!", flush=True)
            print(f"   Message received: {raw_data[:200]}", flush=True)
            print(f"   Available keywords: {[kw for g in GROUPS.values() for kw in g['keywords']]}", flush=True)
            print("═" * 70 + "\n", flush=True)
            
            return jsonify({
                'success': False,
                'error': 'No matching groups',
                'message_received': str(raw_data)[:200]
            }), 200
        
    except Exception as e:
        print(f"\n❌ WEBHOOK ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/buffer', methods=['GET'])
def api_buffer():
    """Get current buffer status"""
    with buffer_lock:
        buf = []
        for gid, msgs in message_buffer.items():
            group_name = next((g['name'] for g in GROUPS.values() if g['group_id'] == gid), 'Unknown')
            buf.append({
                'group_id': gid,
                'group_name': group_name,
                'count': len(msgs),
                'messages': msgs
            })
    
    next_send_in = max(0, 60 - (datetime.now() - last_batch_time).seconds)
    
    return jsonify({
        'buffer': buf,
        'next_send_in_seconds': next_send_in
    }), 200

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Get system statistics"""
    stats = get_stats()
    
    # Add buffered message count
    with buffer_lock:
        buffered = sum(len(m) for m in message_buffer.values())
    stats['buffered_messages'] = buffered
    
    return jsonify(stats), 200

@app.route('/api/messages', methods=['GET'])
def api_all_messages():
    """Get all messages"""
    limit = request.args.get('limit', 50, type=int)
    messages = get_all_messages(limit)
    
    result = []
    for timestamp, message, group_name, keywords in messages:
        # Format timestamp for display
        if DATABASE_TYPE == 'postgresql':
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(timestamp, datetime) else str(timestamp)
        else:
            timestamp_str = timestamp
            
        result.append({
            'timestamp': timestamp_str,
            'message': message,
            'group_name': group_name,
            'keywords': keywords,
            'status': 'sent'
        })
    
    return jsonify({'messages': result}), 200

@app.route('/api/groups', methods=['GET'])
def api_groups():
    """Get all groups with their config"""
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
    """Get users for specific group"""
    try:
        users = get_users_by_group(group_id)
        
        result = []
        current_time = datetime.now()
        
        for user_id, name, invited, expiry, days, status in users:
            try:
                joined = check_user_in_group(group_id, user_id)
                
                # Format dates for display
                if DATABASE_TYPE == 'postgresql':
                    invited_str = invited.strftime('%Y-%m-%d %H:%M:%S') if isinstance(invited, datetime) else str(invited)
                    expiry_str = expiry.strftime('%Y-%m-%d %H:%M:%S') if isinstance(expiry, datetime) else str(expiry)
                    
                    # Parse expiry date
                    if isinstance(expiry, datetime):
                        expiry_date = expiry
                    else:
                        try:
                            expiry_date = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S')
                        except:
                            expiry_date = datetime.strptime(str(expiry), '%Y-%m-%d %H:%M:%S.%f')
                    
                    # Remove timezone info for comparison
                    if hasattr(expiry_date, 'tzinfo') and expiry_date.tzinfo is not None:
                        expiry_date = expiry_date.replace(tzinfo=None)
                else:
                    invited_str = invited
                    expiry_str = expiry
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S')
                
                # Calculate days_left dynamically
                time_diff = expiry_date - current_time
                days_left_calculated = max(0, time_diff.days)
                
                # Skip expired users from display
                if days_left_calculated <= 0:
                    continue  # Don't show expired users
                
                result.append({
                    'user_id': user_id,
                    'name': name,
                    'invited_date': invited_str,
                    'expiry_date': expiry_str,
                    'days_left': days_left_calculated,
                    'status': status,
                    'joined': joined
                })
            except Exception as e:
                print(f"❌ Error processing user {user_id} in group {group_id}: {e}")
                # Continue with next user instead of failing entire request
                continue
        
        return jsonify({'users': result}), 200
    
    except Exception as e:
        print(f"❌ Fatal error in api_group_users for {group_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'users': []}), 200  # Return 200 with empty array instead of 500

@app.route('/api/group/<group_id>/admins', methods=['GET'])
def api_group_admins(group_id):
    """Get all admins from Telegram group"""
    admins = get_group_admins(group_id)
    return jsonify({'admins': admins, 'count': len(admins)}), 200

@app.route('/api/group/<group_id>/messages', methods=['GET'])
def api_group_messages(group_id):
    """Get messages for specific group"""
    limit = request.args.get('limit', 20, type=int)
    messages = get_messages_by_group(group_id, limit)
    
    result = []
    for timestamp, message, keywords in messages:
        # Format timestamp for display
        if DATABASE_TYPE == 'postgresql':
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(timestamp, datetime) else str(timestamp)
        else:
            timestamp_str = timestamp
            
        result.append({
            'timestamp': timestamp_str,
            'message': message,
            'keywords': keywords
        })
    
    return jsonify({'messages': result}), 200

@app.route('/api/user/add', methods=['POST'])
def api_add_user():
    """Add user to group"""
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
    """Extend user expiry"""
    try:
        data = request.json
        
        if data.get('admin_id') != ADMIN_USER_ID:
            return jsonify({'error': 'Unauthorized'}), 403
        
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        days = int(data.get('days', 30))
        
        update_user_expiry(group_id, user_id, days)
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Error in api_extend_user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/reduce', methods=['POST'])
def api_reduce_user():
    """Reduce user expiry"""
    data = request.json
    
    if data.get('admin_id') != ADMIN_USER_ID:
        return jsonify({'error': 'Unauthorized'}), 403
    
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    days = int(data.get('days', 1))
    
    result = reduce_user_expiry(group_id, user_id, days)
    
    if result.get('error'):
        return jsonify({'error': result['error']}), 400
    
    return jsonify({'success': True}), 200

@app.route('/api/user/remove', methods=['POST'])
def api_remove_user():
    """Remove user from group"""
    data = request.json
    
    if data.get('admin_id') != ADMIN_USER_ID:
        return jsonify({'error': 'Unauthorized'}), 403
    
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    
    ban_user_from_group(group_id, user_id)
    remove_user(group_id, user_id)
    
    return jsonify({'success': True}), 200

@app.route('/api/config', methods=['GET'])
def api_config():
    """Get configuration"""
    return jsonify({
        'admin_id': ADMIN_USER_ID,
        'database_type': DATABASE_TYPE
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'database': DATABASE_TYPE}), 200

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 STARTUP
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "═" * 70)
    print("║" + " " * 15 + "TELEGRAM UNIFIED SYSTEM - COMPLETE" + " " * 20 + "║")
    print("═" * 70)
    
    init_database()
    
    print(f"✅ Bot Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    print(f"✅ Database: {DATABASE_TYPE}")
    print(f"✅ Buffer System: ACTIVE (60-second batching)")
    
    print("\n📋 CONFIGURED GROUPS:")
    for key, config in GROUPS.items():
        status = "✅ ACTIVE" if config['enabled'] else "⏸️  DISABLED"
        print(f"   {status} {config['name']}")
        print(f"      Group ID: {config['group_id']}")
        print(f"      Keywords: {', '.join(config['keywords'])}")
    
    print("\n🌐 Server starting...")
    print("📡 Webhook: /webhook/router")
    print("🏠 Dashboard: http://localhost:5000")
    print("⏳ Messages buffered for 60 seconds before sending")
    print("═" * 70)
    print()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
