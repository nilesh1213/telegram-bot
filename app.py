"""
═══════════════════════════════════════════════════════════════════════════
    TELEGRAM UNIFIED SYSTEM - COMPLETE VERSION
    
    Features:
    ✅ 60-second MESSAGE BUFFER system
    ✅ User management (add/extend/reduce/remove)
    ✅ AUTOMATIC USER REMOVAL (kicks from Telegram + removes from database)
    ✅ Multi-database support (SQLite for local, PostgreSQL for production)
    ✅ Real-time dashboard
    ✅ Weekly message cleanup (7 days)
    
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
import logging

app = Flask(__name__, static_folder='static')
CORS(app)

# ═══════════════════════════════════════════════════════════════════════════
# 🔇 SUPPRESS ROUTINE HTTP REQUEST LOGS (only show webhook and user actions)
# ═══════════════════════════════════════════════════════════════════════════

# Disable Flask's default request logging
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Only errors, not INFO requests

# Override Flask's request logger
class SuppressRoutineLogs(logging.Filter):
    def filter(self, record):
        # Suppress routine GET requests for stats, buffer, messages, group users
        if any(x in record.getMessage() for x in ['/api/stats', '/api/buffer', '/api/messages', '/api/group/', 'GET /']):
            return False
        return True

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(SuppressRoutineLogs())

# Custom request logger for important actions only
@app.after_request
def log_important_requests(response):
    """Only log webhook and user management endpoints"""
    if '/webhook/' in request.path or '/api/user/' in request.path:
        print(f"📍 {request.method} {request.path} → {response.status_code}", flush=True)
    return response

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

# Google Sheets - Published CSV URL for Institution Buying stocks (fetched every 5 min)
GOOGLE_SHEETS_CSV_URL = os.environ.get('GOOGLE_SHEETS_CSV_URL', 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQ__Ekh4dVf6dXsVcExivA9OZc2fPAoyRL8gMZ-O7PGrQgGqMln3W5_EBvWmBu53EyJGTawe2fOzBbA/pub?output=csv')

# Cache for institution stocks
institution_stocks_cache = []
institution_stocks_last_fetch = 0  # timestamp
CACHE_DURATION = 300  # 5 minutes

def fetch_institution_stocks():
    """Fetch stock list from Google Sheets. Cache for 5 min. Fallback to hardcoded list."""
    global institution_stocks_cache, institution_stocks_last_fetch
    
    now = time.time()
    # Return cached if fresh (within 5 min)
    if institution_stocks_cache and (now - institution_stocks_last_fetch) < CACHE_DURATION:
        return institution_stocks_cache
    
    try:
        print("📊 Fetching institution stocks from Google Sheets...", flush=True)
        response = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=10)
        if response.status_code == 200:
            stocks = []
            for line in response.text.strip().split('\n'):
                stock = line.strip().strip('"').upper()
                if stock and stock != '':
                    stocks.append(stock)
            
            if stocks:
                institution_stocks_cache = stocks
                institution_stocks_last_fetch = now
                print(f"✅ Fetched {len(stocks)} stocks from Google Sheets", flush=True)
                return stocks
            else:
                print("⚠️ Google Sheets returned empty - using cache/fallback", flush=True)
        else:
            print(f"⚠️ Google Sheets returned {response.status_code} - using cache/fallback", flush=True)
    except Exception as e:
        print(f"⚠️ Google Sheets fetch failed: {e} - using cache/fallback", flush=True)
    
    # Return cache if available, else fallback
    if institution_stocks_cache:
        return institution_stocks_cache
    return INSTITUTION_STOCKS_FALLBACK

# Fallback list if Google Sheets unreachable
INSTITUTION_STOCKS_FALLBACK = [
    'VIJAYPD', 'WALCHANNAG', 'APEX', 'KRISHNADEF', 'OLIL', 'RATNAVEER', 
    'HINDCOPPER', 'ANGELONE', 'ANANTRAJ', 'BSE', 'MCX', 'ONWARDTEC', 
    'SILGO', 'CUPID', 'AWHCL', 'MAGSON', 'CUBEXTUB', 'IBULLSLTD', 
    'ARMOUR', 'ECOSMOBLTY', 'CSSL', 'MTNL', 'RAYMONDLSL', 'RAYMONDREL', 
    'SOUTHBANK', 'MTARTECH', 'ASHWINI', 'IITL', 'AURIGROW', 'SPRL', 
    'INTENTECH', 'PRECAM', 'OMAXAUTO', 'MHLXMIRU', 'KRMAYURVED', 'KCK', 
    'DREDGECORP', 'ANNAPURNA', 'AEROFLEX', 'MALLCOM', 'JKIPL', 'VICTORYEV', 
    'ANTELOPUS', 'GANGAFORGE', 'TEJASNET', 'EXCELINDUS', 'INDIGRID', 
    'BHARATWIRE', 'MUNISH', 'LANDMARK', 'MAHLOG', 'MAXVOLT', 'OBCL', 
    'TNPL', 'DAVANGERE', 'SINTERCOM', 'MANAKALUCO', 'EKC', 'AGIIL', 
    'HOMEFIRST', 'NIKITA', 'OMFURN', 'RACLGEAR', 'VLEGOV', 'ONDOOR', 
    'JTLIND', 'BAJAJCON', 'TANLA', 'RMDRIP', 'RATEGAIN', 'MEDICO', 
    'RALLIS', 'RKSWAMY', 'SBC', 'SIGACHI', 'ARISINFRA', 'SHREEJISPG', 
    'BLUEPEBBLE', 'AEROENTER', 'RNBDENIMS', 'KSR', 'EXCELLENT', 'GENESYS', 
    'BAGDIGITAL', 'DBEIL', 'DCXINDIA', 'AHCL', 'STYLEBAAZA', 'KALYANKJIL', 
    'RBA', 'VPRPL', 'TFCILTD', 'KRISHPP', 'TBZ', 'KANDARP', 'PROPEQUITY', 
    'PATELRMART', 'BAJAJELEC', 'AVANA', 'ABFRL', 'JARO', 'DHARAN', 
    'JINDALSAW', 'VIVIMEDLAB', 'VINEETLAB', 'PRIMECAB', 'ARFIN', 'AMDIND', 
    'CAPTRUST', 'BHARATCOAL', 'CONNPLEX', 'INVICTA', 'ATALREAL', 'PIGL', 
    'IDEALTECHO', 'SPMLINFRA', 'KERNEX', 'SHRINGARMS', 'ARSSBL', 'SOCL', 
    'BESTAGRO', 'PURVA', 'KIRIINDUS', 'QUADFUTURE', 'AAATECH', 'AAVAS', 
    'BALAMINES', 'AVROIND', 'DCMFINSERV', 'INDOWIND', 'JWL', 'GARUDA', 
    'BALUFORGE', 'TARMAT', 'OMAXE', 'JALAN', 'KHANDSE', 'KRYSTAL', 
    'ORIENTTECH', 'MCL', 'AUSOMENT', 'MAITHANALL', 'KESORAMIND', 
    'MIRCELECTR', 'IEX', 'MACOBSTECH', 'MRIL', 'BLISSGVS', 'MODIS', 
    'TIMESCAN', 'AKASH', 'PANACEABIO', 'SHANTIGOLD', 'DHRUV', 'MANGALAM', 
    'EXXARO', 'KAMOPAINTS', 'DEEDEV', 'E2ERAIL', 'RICOAUTO', 'EIMCOELECO', 
    'TARIL', 'SANGANI', 'KROSS', 'SILVERTUC', 'SENCO', 'HILTON-RE1', 
    'FABTECH', 'TVTODAY', 'ARIHANTCAP', 'RADHIKAJWE', 'QUADPRO', 'GKSL', 
    'GATECH', 'ESFL', 'DIVYADHAN', 'SHANKARA', 'SPEB', 'SARTELE', 
    'GANDHAR', 'VCL', 'KAYNES', 'ADVANCE', 'GMBREW', 'DHARIWAL', 
    'DHARARAIL', 'DELPHIFX', 'MINDTECK', 'RAJOOENG', 'SUPREME', 'ENVIRO', 
    'EXIMROUTES', 'CURIS', 'MILTON', 'FIRSTCRY', 'TEMBO', 'TAKE', 
    'MPEL', 'NETWEB', 'SMCGLOBAL', 'FILATFASH', 'IGARASHI', 'SHYAMDHANI', 
    'DURLAX', 'AROGRANITE', 'ZFCVINDIA', 'MARC', 'IDEA', 'GANESHIN'
]

# Pre-fetch on startup
institution_stocks_cache = fetch_institution_stocks()

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
        'enabled': False
    },
    'CASH_ZONE': {
        'name': 'Cash Zone',
        'group_id': os.environ.get('CASH_ZONE_GROUP_ID', '-1003563290768'),
        'keywords': ['NAITIK'],
        'enabled': True
    },
    'FUTURE_ZONE': {
        'name': 'Future Zones',
        'group_id': os.environ.get('FUTURE_ZONE_GROUP_ID', '-1003809222078'),
        'keywords': ['TANISH'],
        'enabled': True
    },
    'SWING': {
        'name': 'Swing and Investment Cash 👉',
        'group_id': os.environ.get('SWING_GROUP_ID', '-1003563158525'),  # CORRECTED
        'keywords': ['SWING'],
        'enabled': True
    },
    'CRYPTO': {
        'name': 'Crypto',
        'group_id': os.environ.get('CRYPTO_GROUP_ID', '-1003641717967'),
        'keywords': ['CRYPTO'],
        'enabled': True
    },
    'CASH_REVERSAL_LONG': {
        'name': 'Cash Reversal Long',
        'group_id': os.environ.get('CASH_REVERSAL_LONG_GROUP_ID', '-1003557486410'),
        'keywords': ['CASH', 'REVERSAL', 'LONG'],
        'enabled': True,
        'parent_group': 'CASH'  # Also sends to Cash Intraday
    },
    'ZONE_REVERSAL_LONG': {
        'name': 'Zone Reversal Long',
        'group_id': os.environ.get('ZONE_REVERSAL_LONG_GROUP_ID', '-1003763196446'),
        'keywords': ['ZONE', 'REVERSAL', 'LONG'],
        'enabled': True,
        'parent_group': 'ZONE'  # Also sends to Zone Signals
    },
    'ZONE_REVERSAL_SHORT': {
        'name': 'Zone Reversal Short',
        'group_id': os.environ.get('ZONE_REVERSAL_SHORT_GROUP_ID', '-1003887891053'),
        'keywords': ['ZONE', 'REVERSAL', 'SHORT'],
        'enabled': True,
        'parent_group': 'ZONE'  # Also sends to Zone Signals
    },
    'STOCK_OPTION_INTRADAY': {
        'name': 'Stock Option Intraday',
        'group_id': os.environ.get('STOCK_OPTION_INTRADAY_GROUP_ID', '-1003742044328'),
        'keywords': ['MOMENTUM'],
        'enabled': True
    },
    'INSTITUTION': {
        'name': 'Institution Buying Shares',
        'group_id': os.environ.get('INSTITUTION_GROUP_ID', '-1003517861259'),
        'keywords': [],  # Fetched dynamically from Google Sheets
        'enabled': False,
        'is_priority': True  # Check this group first
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# ⏱️ RATE LIMITING SYSTEM
# MOMENTUM GROUP: 30-minute window from first message, then BLOCK all messages
# ═══════════════════════════════════════════════════════════════════════════

# Rate limiter configuration - ONLY for STOCK_OPTION_INTRADAY group
RATE_LIMIT_CONFIG = {
    'STOCK_OPTION_INTRADAY': {  # Group key
        'enabled': True,
        'window_minutes': 30,       # 30-minute window from first message
        'keyword': 'MOMENTUM'       # Track messages with this keyword
    }
}

# Track 30-minute window for MOMENTUM group
# Structure: {group_key: {'window_start': timestamp or None}}
rate_limit_tracker = defaultdict(lambda: {'window_start': None})

def check_rate_limit(group_key, message_text):
    """
    MOMENTUM 30-min rule:
      - First message triggers a 30-minute window.
      - All messages WITHIN 30 mins are allowed.
      - After 30 mins, ALL messages are BLOCKED (window resets next day / manual reset).
    Returns: (should_send: bool, reason: str)
    """
    if group_key not in RATE_LIMIT_CONFIG or not RATE_LIMIT_CONFIG[group_key]['enabled']:
        return True, None  # No rate limiting, allow all

    config = RATE_LIMIT_CONFIG[group_key]
    keyword = config['keyword']

    # Only apply rule to MOMENTUM keyword messages
    if keyword.upper() not in message_text.upper():
        return True, None

    tracker = rate_limit_tracker[group_key]
    now = datetime.now()
    window_minutes = config['window_minutes']

    # No window started yet → this is the FIRST message, start the clock
    if tracker['window_start'] is None:
        tracker['window_start'] = now
        window_end = now + timedelta(minutes=window_minutes)
        print(f"⏱️ [MOMENTUM] 30-min window STARTED at {now.strftime('%H:%M:%S')} → closes at {window_end.strftime('%H:%M:%S')}", flush=True)
        return True, None

    # Window already started → check if still within 30 mins
    elapsed = (now - tracker['window_start']).total_seconds() / 60
    window_end = tracker['window_start'] + timedelta(minutes=window_minutes)

    if elapsed <= window_minutes:
        remaining = window_minutes - elapsed
        print(f"✅ [MOMENTUM] Within window ({elapsed:.1f}m elapsed, {remaining:.1f}m remaining)", flush=True)
        return True, None
    else:
        reason = f"30-min window CLOSED (started {tracker['window_start'].strftime('%H:%M')}, ended {window_end.strftime('%H:%M')}). No more MOMENTUM messages."
        print(f"🚫 [MOMENTUM] {reason}", flush=True)
        return False, reason

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
            
            # Take snapshot of buffer and clear it
            buffer_snapshot = {}
            with buffer_lock:
                if message_buffer:
                    for gid, msgs in message_buffer.items():
                        if msgs:
                            buffer_snapshot[gid] = msgs.copy()
                    message_buffer.clear()
            
            # Send buffered messages (only log if there are messages)
            if buffer_snapshot:
                print("\n" + "="*70, flush=True)
                print(f"📤 BUFFER SEND: {len(buffer_snapshot)} group(s)", flush=True)
                
                for idx, (gid, msgs) in enumerate(buffer_snapshot.items()):
                    # Combine all messages for this group
                    combined = "\n\n\n".join([m['message'] for m in msgs])
                    
                    if send_to_telegram(gid, combined):
                        # Log the combined message
                        log_message(combined, gid, msgs[0]['group_name'], 
                                  ", ".join(set([m['keyword'] for m in msgs])))
                        print(f"✅ Sent to {msgs[0]['group_name']} ({len(msgs)} messages)", flush=True)
                    
                    # Delay between groups to avoid rate limits
                    if idx < len(buffer_snapshot) - 1:
                        time.sleep(5)  # 5 seconds between groups
                
                last_batch_time = datetime.now()
                print("="*70 + "\n", flush=True)
                
        except Exception as e:
            print(f"❌ Buffer error: {e}", flush=True)

# Start buffer thread
buffer_thread = threading.Thread(target=process_buffer, daemon=True)
buffer_thread.start()
print("✅ Buffer thread started")

# ═══════════════════════════════════════════════════════════════════════════
# 🗑️ WEEKLY MESSAGE CLEANUP (only messages table, nothing else)
# ═══════════════════════════════════════════════════════════════════════════

def cleanup_old_messages():
    """Background thread - deletes messages older than 7 days every week"""
    while True:
        time.sleep(604800)  # 7 days in seconds
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if DATABASE_TYPE == 'sqlite':
                cursor.execute("DELETE FROM messages WHERE timestamp < datetime('now', '-7 days')")
            elif DATABASE_TYPE == 'postgresql':
                cursor.execute("DELETE FROM messages WHERE timestamp < NOW() - INTERVAL '7 days'")
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"🗑️ Weekly cleanup done - deleted {deleted} old messages", flush=True)
        except Exception as e:
            print(f"❌ Cleanup error: {e}", flush=True)

cleanup_thread = threading.Thread(target=cleanup_old_messages, daemon=True)
cleanup_thread.start()
print("✅ Weekly message cleanup thread started")

# ═══════════════════════════════════════════════════════════════════════════
# 🗑️ AUTOMATIC USER REMOVAL (checks every hour, removes expired users)
# ═══════════════════════════════════════════════════════════════════════════

def auto_remove_expired_users():
    """Background thread - removes expired users from TELEGRAM GROUP + DATABASE"""
    while True:
        time.sleep(60)  # Check every 60 seconds for testing
        try:
            print("\n" + "="*70, flush=True)
            print("🔍 AUTO-REMOVAL CHECK STARTING...", flush=True)
            print("="*70, flush=True)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Find expired users with better error handling
            if DATABASE_TYPE == 'sqlite':
                cursor.execute("""
                    SELECT user_id, group_id, name, expiry_date
                    FROM users 
                    WHERE datetime(expiry_date) < datetime('now')
                """)
            elif DATABASE_TYPE == 'postgresql':
                # More robust: handle both TIMESTAMP and VARCHAR columns
                cursor.execute("""
                    SELECT user_id, group_id, name, expiry_date
                    FROM users 
                    WHERE 
                        CASE 
                            WHEN expiry_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' 
                            THEN TO_TIMESTAMP(expiry_date, 'YYYY-MM-DD HH24:MI:SS') 
                            ELSE expiry_date::TIMESTAMP 
                        END < NOW()
                """)
            
            expired_users = cursor.fetchall()
            
            print(f"📊 Database query completed. Found {len(expired_users)} expired users.", flush=True)
            
            # Show first few for debugging
            if expired_users:
                print("🔍 Sample expired users:", flush=True)
                for i, user in enumerate(expired_users[:3]):
                    print(f"   User {i+1}: ID={user[0]}, Group={user[1]}, Name={user[2]}, Expiry={user[3]}", flush=True)
            
            conn.close()
            
            if expired_users:
                print(f"\n🗑️ Found {len(expired_users)} expired users - removing...", flush=True)
                
                removed_count = 0
                for user_id, group_id, name, expiry_date in expired_users:
                    try:
                        print(f"   Removing {name} (ID: {user_id}) from group {group_id}, expired: {expiry_date}", flush=True)
                        
                        # Ban from Telegram group (kick them out)
                        ban_result = ban_user_from_group(group_id, user_id)
                        if ban_result:
                            print(f"   ✅ Banned from Telegram group", flush=True)
                        else:
                            print(f"   ⚠️ Could not ban from Telegram (maybe already left)", flush=True)
                        
                        # Delete from database
                        remove_user(group_id, user_id)
                        removed_count += 1
                        
                        # Notify user
                        try:
                            send_to_telegram(user_id, "⏰ Your subscription has expired. You have been removed from the group. Please contact admin to renew.")
                        except Exception as notify_error:
                            print(f"   ⚠️ Could not notify user {user_id}: {notify_error}", flush=True)
                        
                        time.sleep(1)  # Delay between removals
                    except Exception as user_error:
                        print(f"   ❌ Failed to remove user {user_id}: {user_error}", flush=True)
                
                print(f"✅ Successfully removed {removed_count}/{len(expired_users)} expired users from Telegram & database", flush=True)
            else:
                print("✅ No expired users to remove", flush=True)
            
            print("="*70 + "\n", flush=True)
                
        except Exception as e:
            print(f"❌ Auto-removal error: {e}", flush=True)
            import traceback
            traceback.print_exc()

auto_remove_thread = threading.Thread(target=auto_remove_expired_users, daemon=True)
auto_remove_thread.start()
print("✅ Automatic user removal thread started (checks hourly)")

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
    """Send message to Telegram group with smart splitting for long messages"""
    MAX_CHUNK_SIZE = 2500  # Target size (well below Telegram's 4096 limit)
    BUFFER_SIZE = 200      # Buffer to avoid breaking messages
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # If message is short enough, send directly
    if len(text) <= MAX_CHUNK_SIZE:
        payload = {'chat_id': int(group_id), 'text': text}
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Failed to send to {group_id}: {e}")
            try:
                error_details = response.json()
                print(f"   Telegram API Response: {error_details}")
            except:
                pass
            return False
    
    # Message is too long - need to split intelligently
    print(f"📏 Message is {len(text)} chars - splitting into chunks...")
    
    # Split by message separator (3 newlines between messages)
    individual_messages = text.split("\n\n\n")
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for msg in individual_messages:
        msg_length = len(msg)
        
        # If adding this message would exceed limit (with buffer)
        if current_length + msg_length + 3 > MAX_CHUNK_SIZE - BUFFER_SIZE:
            # Save current chunk if it has content
            if current_chunk:
                chunks.append("\n\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # If single message is too long, we still need to send it
            # (Telegram limit is 4096, so 2500+ single messages will still go through)
            if msg_length > MAX_CHUNK_SIZE:
                chunks.append(msg)
            else:
                current_chunk = [msg]
                current_length = msg_length
        else:
            # Add message to current chunk
            current_chunk.append(msg)
            current_length += msg_length + 3  # +3 for separator
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append("\n\n\n".join(current_chunk))
    
    print(f"✂️ Split into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"   Chunk {i+1}: {len(chunk)} characters")
    
    # Send all chunks with small delay between them
    all_sent = True
    for i, chunk in enumerate(chunks):
        payload = {'chat_id': int(group_id), 'text': chunk}
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"✅ Sent chunk {i+1}/{len(chunks)}")
            
            # Small delay between chunks (except for last one)
            if i < len(chunks) - 1:
                time.sleep(1)
        except Exception as e:
            print(f"❌ Failed to send chunk {i+1}/{len(chunks)} to {group_id}: {e}")
            try:
                error_details = response.json()
                print(f"   Telegram API Response: {error_details}")
            except:
                pass
            all_sent = False
    
    return all_sent

def create_invite_link(group_id, expire_days=30):
    """Create invite link for group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
    expire_date = int(time.time()) + (expire_days * 86400)
    payload = {'chat_id': int(group_id), 'expire_date': expire_date, 'member_limit': 1}
    
    print(f"🔄 Creating invite link for group_id={group_id}, payload={payload}", flush=True)
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        print(f"📩 Telegram response: {data}", flush=True)
        
        if data.get('ok'):
            return {'success': True, 'link': data['result']['invite_link']}
        
        # Return exact error from Telegram
        print(f"❌ Telegram error: {data.get('error_code')} - {data.get('description')}", flush=True)
        return {'success': False, 'error': data.get('description', 'Unknown error')}
    except Exception as e:
        print(f"❌ Failed to create invite link: {e}", flush=True)
        return {'success': False, 'error': str(e)}

def check_user_in_group(group_id, user_id):
    """Check if user is in group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
    
    try:
        response = requests.post(url, json={'chat_id': int(group_id), 'user_id': int(user_id)}, timeout=10)
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
        response = requests.post(url, json={'chat_id': int(group_id), 'user_id': int(user_id)}, timeout=10)
        response.raise_for_status()
        
        # Unban so they can be re-invited later
        unban_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/unbanChatMember"
        requests.post(unban_url, json={'chat_id': int(group_id), 'user_id': int(user_id), 'only_if_banned': True})
        
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
        response = requests.get(url, params={'chat_id': int(group_id)}, timeout=10)
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
    """Add user to group - ALWAYS store as strings for consistency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert to strings for consistent storage
    group_id = str(group_id)
    user_id = str(user_id)
    
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
    print(f"✅ User {user_id} added to database for group {group_id}", flush=True)

def get_users_by_group(group_id):
    """Get all users for a specific group - use string for consistency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert to string for consistent querying
    group_id = str(group_id)
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'''
        SELECT user_id, name, invited_date, expiry_date, days_left, status
        FROM users
        WHERE group_id = {placeholder}
        ORDER BY invited_date DESC
    ''', (group_id,))
    
    users = cursor.fetchall()
    conn.close()
    print(f"📊 Retrieved {len(users)} users for group {group_id}", flush=True)
    return users

def update_user_expiry(group_id, user_id, additional_days):
    """Extend user expiry - use strings for consistency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert to strings
    group_id = str(group_id)
    user_id = str(user_id)
    
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
            # Parse the result - it might be datetime or string
            if isinstance(result[0], str):
                # It's a string, parse it
                try:
                    current_expiry = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Try with microseconds
                    current_expiry = datetime.strptime(result[0].split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                # It's already a datetime object
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
    
    # Convert to strings
    group_id = str(group_id)
    user_id = str(user_id)
    
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
            # Parse the result - it might be datetime or string
            if isinstance(result[0], str):
                # It's a string, parse it
                try:
                    current_expiry = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    # Try with microseconds
                    current_expiry = datetime.strptime(result[0].split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                # It's already a datetime object
                current_expiry = result[0]
                # Remove timezone for comparison if present
                if hasattr(current_expiry, 'tzinfo') and current_expiry.tzinfo is not None:
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
    """Remove user from database - use strings for consistency"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert to strings
    group_id = str(group_id)
    user_id = str(user_id)
    
    placeholder = '?' if DATABASE_TYPE == 'sqlite' else '%s'
    cursor.execute(f'DELETE FROM users WHERE group_id = {placeholder} AND user_id = {placeholder}', (group_id, user_id))
    
    conn.commit()
    conn.close()
    print(f"🗑️ User {user_id} removed from database for group {group_id}", flush=True)

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
        
        print(f"\n📥 ALERT: {str(raw_data)[:100]}...", flush=True)
        
        # Route to appropriate groups based on keywords
        message_upper = str(raw_data).upper()
        routed_to = []
        matched_groups = set()  # Track which groups already matched to avoid duplicates
        
        # 🔥 STEP 1: Find Institution stock keyword (DON'T send yet - wait for CASH+LONG check)
        institution_group = GROUPS.get('INSTITUTION')
        institution_stock_found = None
        
        if institution_group and institution_group['enabled'] and institution_group.get('is_priority'):
            # Fetch fresh stock list from Google Sheets (cached 5 min)
            institution_keywords = fetch_institution_stocks()
            for keyword in institution_keywords:
                if keyword.upper() in message_upper:
                    institution_stock_found = keyword
                    print(f"   📌 INSTITUTION STOCK FOUND: '{keyword}' - waiting for CASH+LONG check", flush=True)
                    break  # Only need one stock match
        
        # 🔥 STEP 2: Institution Buying ONLY when CASH + LONG + stock ALL present
        has_cash = 'CASH' in message_upper
        has_long = 'LONG' in message_upper
        cash_long_institution = has_cash and has_long and institution_stock_found
        
        if cash_long_institution:
            # Send to Institution Buying
            group_id = institution_group['group_id']
            group_name = institution_group['name']
            print(f"   ✅ CASH + LONG + {institution_stock_found}! Sending to Institution Buying!", flush=True)
            if group_id not in matched_groups:
                add_to_buffer(group_id, group_name, str(raw_data), institution_stock_found)
                routed_to.append({'group_name': group_name})
                matched_groups.add(group_id)
            
            # Also send to Cash Intraday
            cash_group = GROUPS.get('CASH')
            if cash_group and cash_group['enabled']:
                cash_gid = cash_group['group_id']
                cash_gname = cash_group['name']
                print(f"   ✅ Also sending to Cash Intraday!", flush=True)
                if cash_gid not in matched_groups:
                    add_to_buffer(cash_gid, cash_gname, str(raw_data), f"CASH+{institution_stock_found}")
                    routed_to.append({'group_name': cash_gname})
                    matched_groups.add(cash_gid)
        else:
            if institution_stock_found:
                print(f"   🚫 Stock '{institution_stock_found}' found but no CASH+LONG - skipping Institution", flush=True)
        
        # 🔥 STEP 3: Check Reversal Groups (flexible word match - ALL words must be present anywhere)
        # BUT skip CASH_REVERSAL_LONG if cash_long_institution is True
        REVERSAL_GROUPS = ['CASH_REVERSAL_LONG', 'ZONE_REVERSAL_LONG', 'ZONE_REVERSAL_SHORT']
        
        for rev_key in REVERSAL_GROUPS:
            # Skip CASH_REVERSAL_LONG when CASH+LONG+Institution stock present
            if rev_key == 'CASH_REVERSAL_LONG' and cash_long_institution:
                print(f"   🚫 Skipping CASH_REVERSAL_LONG - Institution stock present", flush=True)
                continue
            rev_group = GROUPS.get(rev_key)
            if not rev_group or not rev_group['enabled']:
                continue
            
            # Check if ALL keywords present anywhere in message (flexible matching)
            all_words_found = all(word.upper() in message_upper for word in rev_group['keywords'])
            
            if all_words_found:
                group_id = rev_group['group_id']
                group_name = rev_group['name']
                
                print(f"   ✅ REVERSAL MATCH! '{rev_key}' - all words found!", flush=True)
                
                # Send to reversal group
                if group_id not in matched_groups:
                    add_to_buffer(group_id, group_name, str(raw_data), ' '.join(rev_group['keywords']))
                    routed_to.append({'group_name': group_name})
                    matched_groups.add(group_id)
                
                # Send to parent group too
                parent_key = rev_group.get('parent_group')
                if parent_key:
                    parent_group = GROUPS.get(parent_key)
                    if parent_group and parent_group['enabled']:
                        parent_id = parent_group['group_id']
                        parent_name = parent_group['name']
                        
                        print(f"   ✅ DUAL-SEND to parent: {parent_name}", flush=True)
                        
                        if parent_id not in matched_groups:
                            add_to_buffer(parent_id, parent_name, str(raw_data), f"{rev_key}→{parent_key}")
                            routed_to.append({'group_name': parent_name})
                            matched_groups.add(parent_id)
        
        # 🔥 STEP 4: Regular routing for all other groups
        for group_key, group_config in GROUPS.items():
            if not group_config['enabled']:
                print(f"⏸️  Skipping disabled group: {group_config['name']}", flush=True)
                continue
            
            # Skip Institution (already checked in STEP 1) and Reversal groups (already checked in STEP 3)
            if group_config.get('is_priority') or group_config.get('parent_group'):
                continue
            
            for keyword in group_config['keywords']:
                print(f"   Checking keyword '{keyword}' in message...", flush=True)
                if keyword.upper() in message_upper:
                    group_id = group_config['group_id']
                    group_name = group_config['name']
                    
                    print(f"   ✅ MATCH! Keyword '{keyword}' found!", flush=True)
                    
                    # ⏱️ CHECK RATE LIMIT before adding to buffer
                    should_send, rate_limit_reason = check_rate_limit(group_key, str(raw_data))
                    
                    if not should_send:
                        print(f"   🚫 RATE LIMITED: {rate_limit_reason}", flush=True)
                        continue  # Skip this group, move to next
                    
                    # Avoid duplicate sends
                    if group_id not in matched_groups:
                        add_to_buffer(group_id, group_name, str(raw_data), keyword)
                        routed_to.append({'group_name': group_name})
                        matched_groups.add(group_id)
                    
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
        # For INSTITUTION, return live stock list from Google Sheets
        keywords = fetch_institution_stocks() if key == 'INSTITUTION' else config['keywords']
        groups_list.append({
            'key': key,
            'name': config['name'],
            'group_id': config['group_id'],
            'keywords': keywords,
            'enabled': config['enabled']
        })
    
    return jsonify({'groups': groups_list}), 200

@app.route('/api/rate-limit/status', methods=['GET'])
def api_rate_limit_status():
    """Get current rate limit status for all rate-limited groups"""
    status = []
    
    for group_key, config in RATE_LIMIT_CONFIG.items():
        if not config['enabled']:
            continue
        
        tracker = rate_limit_tracker[group_key]
        current_window = get_current_5min_window()
        
        # Get group name from GROUPS config
        group_name = GROUPS.get(group_key, {}).get('name', group_key)
        
        if tracker['window_start'] is None or tracker['window_start'] != current_window:
            # New window or no messages yet
            window_end = current_window + timedelta(minutes=config['window_minutes'])
            status.append({
                'group_key': group_key,
                'group_name': group_name,
                'keyword': config['keyword'],
                'current_window': f"{current_window.strftime('%H:%M')}-{window_end.strftime('%H:%M')}",
                'messages_sent': 0,
                'max_messages': config['max_messages_per_window'],
                'remaining': config['max_messages_per_window'],
                'is_limited': False
            })
        else:
            # Active window
            window_end = tracker['window_start'] + timedelta(minutes=config['window_minutes'])
            remaining = max(0, config['max_messages_per_window'] - tracker['count'])
            
            status.append({
                'group_key': group_key,
                'group_name': group_name,
                'keyword': config['keyword'],
                'current_window': f"{tracker['window_start'].strftime('%H:%M')}-{window_end.strftime('%H:%M')}",
                'messages_sent': tracker['count'],
                'max_messages': config['max_messages_per_window'],
                'remaining': remaining,
                'is_limited': tracker['count'] >= config['max_messages_per_window'],
                'recent_messages': [
                    {
                        'time': msg['time'].strftime('%H:%M:%S'),
                        'text': msg['text']
                    } for msg in tracker['messages'][-5:]  # Last 5 messages
                ]
            })
    
    return jsonify({
        'rate_limits': status,
        'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200

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
                
                # Enhanced logging for users with < 1 day remaining
                if days_left_calculated < 1 and time_diff.total_seconds() > 0:
                    hours_left = int(time_diff.total_seconds() / 3600)
                    minutes_left = int((time_diff.total_seconds() % 3600) / 60)
                    print(f"   ⏰ User {user_id} ({name}): {hours_left}h {minutes_left}m until expiry | Added: {invited_str} | Expires: {expiry_str}", flush=True)
                
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
    
    # Convert to int - Telegram API needs integer, not string
    group_id = int(group_id)
    user_id = int(user_id)
    
    invite_result = create_invite_link(group_id, days)
    
    if not invite_result.get('success'):
        actual_error = invite_result.get('error', 'Unknown error')
        print(f"❌ Invite link failed for group {group_id}: {actual_error}", flush=True)
        return jsonify({'error': f'Telegram says: {actual_error}'}), 500
    
    invite_link = invite_result['link']
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
        
        group_id = int(group_id)
        user_id = int(user_id)
        
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
    try:
        data = request.json
        
        if data.get('admin_id') != ADMIN_USER_ID:
            return jsonify({'error': 'Unauthorized'}), 403
        
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        days = int(data.get('days', 1))
        
        group_id = int(group_id)
        user_id = int(user_id)
        
        result = reduce_user_expiry(group_id, user_id, days)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Error in api_reduce_user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/remove', methods=['POST'])
def api_remove_user():
    """Remove user from group (MANUAL: bans from Telegram + removes from database)"""
    try:
        data = request.json
        
        if data.get('admin_id') != ADMIN_USER_ID:
            return jsonify({'error': 'Unauthorized'}), 403
        
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        
        group_id = int(group_id)
        user_id = int(user_id)
        
        # Manual removal: Ban from Telegram AND remove from database
        ban_user_from_group(group_id, user_id)
        remove_user(group_id, user_id)
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Error in api_remove_user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def api_config():
    """Get configuration"""
    return jsonify({
        'admin_id': ADMIN_USER_ID,
        'database_type': DATABASE_TYPE
    }), 200


@app.route('/api/momentum/reset', methods=['POST'])
def api_reset_momentum_window():
    """Manually reset the 30-minute Momentum window (admin only)"""
    try:
        data = request.json or {}
        if str(data.get('admin_id')) != str(ADMIN_USER_ID):
            return jsonify({'error': 'Unauthorized'}), 403

        old_start = rate_limit_tracker['STOCK_OPTION_INTRADAY'].get('window_start')
        rate_limit_tracker['STOCK_OPTION_INTRADAY']['window_start'] = None
        print(f"🔄 [MOMENTUM] Window manually RESET by admin (was: {old_start})", flush=True)
        return jsonify({'success': True, 'message': 'Momentum 30-min window reset. Next MOMENTUM message will start a new window.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/momentum/status', methods=['GET'])
def api_momentum_status():
    """Check current Momentum window status"""
    tracker = rate_limit_tracker['STOCK_OPTION_INTRADAY']
    window_start = tracker.get('window_start')

    if window_start is None:
        return jsonify({'status': 'READY', 'message': 'No active window. Next MOMENTUM message will start the 30-min clock.'}), 200

    now = datetime.now()
    elapsed = (now - window_start).total_seconds() / 60
    window_end = window_start + timedelta(minutes=30)

    if elapsed <= 30:
        remaining = 30 - elapsed
        return jsonify({
            'status': 'ACTIVE',
            'window_start': window_start.strftime('%H:%M:%S'),
            'window_end': window_end.strftime('%H:%M:%S'),
            'elapsed_minutes': round(elapsed, 1),
            'remaining_minutes': round(remaining, 1)
        }), 200
    else:
        return jsonify({
            'status': 'CLOSED',
            'message': f'Window closed at {window_end.strftime("%H:%M")}. No MOMENTUM messages allowed. Use /api/momentum/reset to reset.'
        }), 200


@app.route('/api/check-bot/<group_id>', methods=['GET'])
def check_bot_permissions(group_id):
    """Diagnostic: Check bot permissions on a group"""
    try:
        gid = int(group_id)
        
        # 1. Check if bot can see the group
        chat_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChat"
        chat_resp = requests.post(chat_url, json={'chat_id': gid}, timeout=10)
        chat_data = chat_resp.json()
        
        if not chat_data.get('ok'):
            return jsonify({'error': f"Cannot access group: {chat_data.get('description')}"}), 200
        
        chat_info = chat_data['result']
        
        # 2. Check bot own status in the group
        me_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        me_resp = requests.get(me_url, timeout=10)
        me_data = me_resp.json()
        bot_id = me_data['result']['id']
        
        member_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember"
        member_resp = requests.post(member_url, json={'chat_id': gid, 'user_id': bot_id}, timeout=10)
        member_data = member_resp.json()
        
        # 3. Try creating invite link
        invite_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
        invite_resp = requests.post(invite_url, json={'chat_id': gid, 'expire_date': int(time.time()) + 3600, 'member_limit': 1}, timeout=10)
        invite_data = invite_resp.json()
        
        return jsonify({
            'group_id': gid,
            'group_type': chat_info.get('type'),
            'group_title': chat_info.get('title'),
            'bot_id': bot_id,
            'bot_status_in_group': member_data.get('result', {}).get('status', 'NOT FOUND'),
            'bot_permissions': member_data.get('result', {}),
            'invite_link_result': invite_data
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/sheets', methods=['GET'])
def debug_sheets():
    """Debug Google Sheets fetch - shows exact URL, status, response"""
    try:
        print(f"🔍 DEBUG: Fetching {GOOGLE_SHEETS_CSV_URL}", flush=True)
        response = requests.get(GOOGLE_SHEETS_CSV_URL, timeout=10)
        return jsonify({
            'url': GOOGLE_SHEETS_CSV_URL,
            'status_code': response.status_code,
            'response_text': response.text[:500],
            'cache_count': len(institution_stocks_cache),
            'cache_stocks': institution_stocks_cache[:10]
        }), 200
    except Exception as e:
        return jsonify({
            'url': GOOGLE_SHEETS_CSV_URL,
            'error': str(e),
            'cache_count': len(institution_stocks_cache),
            'cache_stocks': institution_stocks_cache[:10]
        }), 500

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
    print(f"✅ Auto-Removal: ACTIVE (checks every hour for expired users)")
    
    print("\n📋 CONFIGURED GROUPS:")
    for key, config in GROUPS.items():
        status = "✅ ACTIVE" if config['enabled'] else "⏸️  DISABLED"
        rate_limit_info = ""
        if key in RATE_LIMIT_CONFIG and RATE_LIMIT_CONFIG[key]['enabled']:
            rl_cfg = RATE_LIMIT_CONFIG[key]
            rate_limit_info = f" [⏱️ 30-MIN WINDOW from first message]"
        print(f"   {status} {config['name']}{rate_limit_info}")
        print(f"      Group ID: {config['group_id']}")
        print(f"      Keywords: {', '.join(config['keywords'])}")
    
    print("\n🌐 Server starting...")
    print("📡 Webhook: /webhook/router")
    print("🏠 Dashboard: http://localhost:5000")
    print("⏳ Messages buffered for 60 seconds before sending")
    print("🗑️ Expired users automatically removed every hour")
    print("═" * 70)
    print()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
