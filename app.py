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

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "8435296160:AAGERJ9ZGwlgR578OUcil84wrGLVrb8Ej7A")
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID', "8363089809")

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    DATABASE_TYPE = 'postgresql'
else:
    from pathlib import Path
    DATABASE_URL = str(Path(__file__).resolve().parent / 'unified_system.db')
    DATABASE_TYPE = 'sqlite'

GROUPS = {
    'ZONE': {'name': 'Zone Signals', 'group_id': os.environ.get('ZONE_GROUP_ID', '-1003668316027'), 'keywords': ['ZONE'], 'enabled': True},
    'INDEX': {'name': 'Index Option Buying', 'group_id': os.environ.get('INDEX_GROUP_ID', '-5286555501'), 'keywords': ['OPTION'], 'enabled': True},
    'COMMODITY': {'name': 'Commodity', 'group_id': os.environ.get('COMMODITY_GROUP_ID', '-5052531894'), 'keywords': ['COMMODITY'], 'enabled': True}
}

message_buffer = defaultdict(list)
buffer_lock = threading.Lock()
last_batch_time = datetime.now()

def get_db_connection():
    if DATABASE_TYPE == 'sqlite':
        import sqlite3
        return sqlite3.connect(DATABASE_URL, check_same_thread=False)
    else:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)

def send_to_telegram(group_id, text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={'chat_id': group_id, 'text': text}, timeout=10).raise_for_status()
        return True
    except:
        return False

def log_message(message, group_id, group_name, keywords):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (timestamp, message, group_id, group_name, matched_keywords) VALUES (%s, %s, %s, %s, %s)", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message, group_id, group_name, keywords))
        conn.commit()
        conn.close()
    except:
        pass

def add_to_buffer(group_id, group_name, message, keyword):
    with buffer_lock:
        message_buffer[group_id].append({'message': message, 'group_name': group_name, 'keyword': keyword, 'received_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

def process_buffer():
    global last_batch_time
    print("🔄 Buffer thread starting...")
    while True:
        try:
            time.sleep(60)
            print("⏰ Buffer cycle - checking for messages...")
            buffer_snapshot = {}
            with buffer_lock:
                if message_buffer:
                    for gid, msgs in message_buffer.items():
                        if msgs:
                            buffer_snapshot[gid] = msgs.copy()
                    message_buffer.clear()
            if buffer_snapshot:
                print(f"📤 Sending {len(buffer_snapshot)} group(s)")
                for idx, (gid, msgs) in enumerate(buffer_snapshot.items()):
                    combined = "\n\n\n".join([m['message'] for m in msgs])
                    if send_to_telegram(gid, combined):
                        log_message(combined, gid, msgs[0]['group_name'], ", ".join(set([m['keyword'] for m in msgs])))
                        print(f"✅ Sent to {msgs[0]['group_name']}")
                    if idx < len(buffer_snapshot) - 1:
                        time.sleep(10)
                last_batch_time = datetime.now()
        except Exception as e:
            print(f"❌ Buffer error: {e}")

buffer_thread = threading.Thread(target=process_buffer, daemon=True)
buffer_thread.start()
print("✅ Buffer thread started")

@app.route('/')
def home():
    return send_from_directory('static', 'index.html')

@app.route('/webhook/router', methods=['POST'])
def webhook():
    raw = request.data.decode('utf-8')
    if not raw:
        return jsonify({'error': 'No data'}), 400
    routed = []
    for gk, gc in GROUPS.items():
        if gc['enabled']:
            for kw in gc['keywords']:
                if kw.upper() in raw.upper():
                    add_to_buffer(gc['group_id'], gc['name'], raw, kw)
                    routed.append({'group_name': gc['name']})
                    break
    return jsonify({'success': bool(routed), 'groups': [r['group_name'] for r in routed]}), 200

@app.route('/api/buffer', methods=['GET'])
def api_buffer():
    with buffer_lock:
        buf = [{'group_id': gid, 'group_name': next((g['name'] for g in GROUPS.values() if g['group_id'] == gid), 'Unknown'), 'count': len(msgs), 'messages': msgs} for gid, msgs in message_buffer.items()]
    return jsonify({'buffer': buf, 'next_send_in_seconds': max(0, 60 - (datetime.now() - last_batch_time).seconds)}), 200

@app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM messages')
        total = cursor.fetchone()[0]
        conn.close()
    except:
        total = 0
    with buffer_lock:
        buffered = sum(len(m) for m in message_buffer.values())
    return jsonify({'total_users': 0, 'active_users': 0, 'total_messages': total, 'enabled_groups': 3, 'buffered_messages': buffered}), 200

@app.route('/api/messages', methods=['GET'])
def api_messages():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT timestamp, message, group_name, matched_keywords FROM messages ORDER BY id DESC LIMIT 50')
        msgs = [{'timestamp': t, 'message': m, 'group_name': gn, 'keywords': kw, 'status': 'sent'} for t, m, gn, kw in cursor.fetchall()]
        conn.close()
        return jsonify({'messages': msgs}), 200
    except:
        return jsonify({'messages': []}), 200

@app.route('/api/groups', methods=['GET'])
def api_groups():
    return jsonify({'groups': [{'key': k, 'name': v['name'], 'group_id': v['group_id'], 'keywords': v['keywords'], 'enabled': v['enabled']} for k, v in GROUPS.items()]}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))