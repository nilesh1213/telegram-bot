"""
═══════════════════════════════════════════════════════════════════════════
    TELEGRAM UNIFIED SYSTEM - BACKEND
    
    Deployment ready for:
    - Railway
    - Render
    - AWS EC2
    - Heroku
    - DigitalOcean
    
    Database support:
    - PostgreSQL (Railway/Render default)
    - MySQL (AWS RDS)
    - SQLite (local testing)
═══════════════════════════════════════════════════════════════════════════
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import time
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "8435296160:AAGERJ9ZGwlgR578OUcil84wrGLVrb8Ej7A")
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID', "8363089809")

# Database Configuration
DATABASE_TYPE = os.environ.get('DATABASE_TYPE', 'sqlite')  # sqlite, postgresql, mysql
DATABASE_URL = os.environ.get('DATABASE_URL', 'unified_system.db')

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
        'keywords': ['INDEX', 'NIFTY', 'BANKNIFTY'],
        'enabled': False
    },
    'COMMODITY': {
        'name': 'Commodity',
        'group_id': os.environ.get('COMMODITY_GROUP_ID', '-5052531894'),
        'keywords': ['COMMODITY', 'GOLD', 'CRUDE'],
        'enabled': False
    }
}

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
    elif DATABASE_TYPE == 'mysql':
        import mysql.connector
        from urllib.parse import urlparse
        parsed = urlparse(DATABASE_URL)
        return mysql.connector.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:]
        )
    else:
        raise ValueError(f"Unsupported database type: {DATABASE_TYPE}")

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
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
                matched_keywords TEXT
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
                matched_keywords VARCHAR(200)
            )
        ''')
    
    elif DATABASE_TYPE == 'mysql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(100),
                group_id VARCHAR(100),
                name VARCHAR(200),
                invited_date VARCHAR(50),
                expiry_date VARCHAR(50),
                days_left INT,
                status VARCHAR(20),
                PRIMARY KEY (user_id, group_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp VARCHAR(50),
                message TEXT,
                group_id VARCHAR(100),
                group_name VARCHAR(200),
                matched_keywords VARCHAR(200)
            )
        ''')
    
    conn.commit()
    conn.close()

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
    elif DATABASE_TYPE == 'mysql':
        cursor.execute('''
            INSERT INTO users 
            (user_id, group_id, name, invited_date, expiry_date, days_left, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'active')
            ON DUPLICATE KEY UPDATE
            name=%s, invited_date=%s, expiry_date=%s, days_left=%s, status='active'
        ''', (user_id, group_id, name, invited_date, expiry_date, days, name, invited_date, expiry_date, days))
    
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
        current_expiry = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        new_expiry = current_expiry + timedelta(days=additional_days)
        new_expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute(f'''
            UPDATE users
            SET expiry_date = {placeholder}, days_left = days_left + {placeholder}
            WHERE group_id = {placeholder} AND user_id = {placeholder}
        ''', (new_expiry_str, additional_days, group_id, user_id))
        
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        INSERT INTO messages (timestamp, message, group_id, group_name, matched_keywords)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
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
# 🎯 MESSAGE ROUTING
# ═══════════════════════════════════════════════════════════════════════════

def route_message(message):
    """Route message to appropriate groups based on keywords"""
    message_upper = message.upper()
    sent_to = []
    
    for group_key, group_config in GROUPS.items():
        if not group_config['enabled']:
            continue
        
        for keyword in group_config['keywords']:
            if keyword.upper() in message_upper:
                group_id = group_config['group_id']
                group_name = group_config['name']
                
                if send_to_telegram(group_id, message):
                    sent_to.append({
                        'group_id': group_id,
                        'group_name': group_name,
                        'keyword': keyword
                    })
                    
                    log_message(message, group_id, group_name, keyword)
                    print(f"✅ Sent to {group_name}")
                
                break
    
    return sent_to

# ═══════════════════════════════════════════════════════════════════════════
# 🌐 API ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """Serve frontend HTML"""
    return send_from_directory('static', 'index.html')

@app.route('/webhook/router', methods=['POST'])
def webhook_router():
    """Main webhook - receives TradingView alerts"""
    try:
        raw_data = request.data.decode('utf-8')
        
        if not raw_data:
            return jsonify({'error': 'No data received'}), 400
        
        print("\n" + "═" * 70)
        print("🔔 ALERT RECEIVED")
        print("═" * 70)
        print(f"Message: {raw_data}")
        print("─" * 70)
        
        sent_to = route_message(raw_data)
        
        if sent_to:
            print(f"✅ Sent to {len(sent_to)} group(s)")
            for item in sent_to:
                print(f"   → {item['group_name']} (keyword: {item['keyword']})")
            print("═" * 70 + "\n")
            
            return jsonify({
                'success': True,
                'sent_to_groups': len(sent_to),
                'groups': [item['group_name'] for item in sent_to]
            }), 200
        else:
            print("⚠️ No groups matched")
            print("═" * 70 + "\n")
            
            return jsonify({
                'success': False,
                'error': 'No matching groups'
            }), 200
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def api_config():
    """Get configuration"""
    return jsonify({
        'admin_id': ADMIN_USER_ID,
        'database_type': DATABASE_TYPE
    }), 200

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Get system statistics"""
    stats = get_stats()
    return jsonify(stats), 200

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
    users = get_users_by_group(group_id)
    
    result = []
    for user_id, name, invited, expiry, days, status in users:
        joined = check_user_in_group(group_id, user_id)
        
        result.append({
            'user_id': user_id,
            'name': name,
            'invited_date': invited,
            'expiry_date': expiry,
            'days_left': days,
            'status': status,
            'joined': joined
        })
    
    return jsonify({'users': result}), 200

@app.route('/api/group/<group_id>/admins', methods=['GET'])
def api_group_admins(group_id):
    """Get all admins from Telegram group"""
    admins = get_group_admins(group_id)
    return jsonify({'admins': admins, 'count': len(admins)}), 200

@app.route('/api/group/<group_id>/messages', methods=['GET'])
def api_group_messages(group_id):
    """Get messages for specific group"""
    limit = request.args.get('limit', 50, type=int)
    messages = get_messages_by_group(group_id, limit)
    
    result = []
    for timestamp, message, keywords in messages:
        result.append({
            'timestamp': timestamp,
            'message': message,
            'keywords': keywords
        })
    
    return jsonify({'messages': result}), 200

@app.route('/api/messages', methods=['GET'])
def api_all_messages():
    """Get all messages"""
    limit = request.args.get('limit', 100, type=int)
    messages = get_all_messages(limit)
    
    result = []
    for timestamp, message, group_name, keywords in messages:
        result.append({
            'timestamp': timestamp,
            'message': message,
            'group_name': group_name,
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
    data = request.json
    
    if data.get('admin_id') != ADMIN_USER_ID:
        return jsonify({'error': 'Unauthorized'}), 403
    
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    days = int(data.get('days', 30))
    
    update_user_expiry(group_id, user_id, days)
    
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

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'database': DATABASE_TYPE}), 200

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 STARTUP
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "═" * 70)
    print("║" + " " * 18 + "TELEGRAM UNIFIED SYSTEM" + " " * 29 + "║")
    print("═" * 70)
    
    init_database()
    print("✅ Database initialized")
    
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
    print("═" * 70)
    print()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
