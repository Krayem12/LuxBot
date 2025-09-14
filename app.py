from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import time
import random

app = Flask(__name__)

# Saudi time settings (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_CONFIRMATION_SIGNALS = 1  # إشارة واحدة للتأكيد
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# تخزين آخر اتجاه عام
last_trend_direction = None
last_trend_message = ""

# Cache for processed signals
signal_cache = {}
CACHE_TIMEOUT = 300

# Optimized get Saudi time
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# Optimized HTML tag removal
def remove_html_tags(text):
    if not text:
        return text
    return re.sub('<.*?>', '', text)

# Optimized Telegram sending
session = requests.Session()
def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = session.post(url, json=payload, timeout=3)
        return response.status_code == 200
            
    except Exception:
        return False

# Optimized stock list loading
_stock_list_cache = None
_stock_list_cache_time = 0
def load_stocks():
    global _stock_list_cache, _stock_list_cache_time
    
    if _stock_list_cache and time.time() - _stock_list_cache_time < 300:
        return _stock_list_cache
    
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]
    
    _stock_list_cache = stocks
    _stock_list_cache_time = time.time()
    return stocks

# Stock list
STOCK_LIST = load_stocks()

# Optimized signal memory
MAX_SIGNALS_PER_SYMBOL = 20
signal_memory = defaultdict(lambda: {
    "bullish": [], 
    "bearish": [],
    "trend_bullish": False,
    "trend_bearish": False
})

# Optimized external POST
def send_post_request(message, indicators, signal_type=None):
    try:
        url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
        clean_message = remove_html_tags(message)
        
        payload = {
            "text": clean_message,
            "extras": {
                "indicators": indicators,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "tradingview-bot",
                "original_signal_type": signal_type
            }
        }
        
        response = session.post(url, json=payload, timeout=3)
        return response.status_code == 200
            
    except Exception:
        return False

# Optimized cleanup
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    cleanup_count = 0
    
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            original_count = len(signal_memory[symbol][direction])
            signal_memory[symbol][direction] = [
                (sig, ts) for sig, ts in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
            cleanup_count += (original_count - len(signal_memory[symbol][direction]))
            
            if len(signal_memory[symbol][direction]) > MAX_SIGNALS_PER_SYMBOL:
                signal_memory[symbol][direction] = signal_memory[symbol][direction][-MAX_SIGNALS_PER_SYMBOL:]
        
        if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
            del signal_memory[symbol]
    
    if cleanup_count > 0:
        print(f"🧹 Cleaned {cleanup_count} old signals")

# Improved symbol extraction - better handling of various formats
def extract_symbol(message):
    message_upper = message.upper().strip()
    
    # First check for known symbols in the message
    for symbol in STOCK_LIST:
        if symbol in message_upper:
            return symbol
    
    # Check for common patterns
    symbol_patterns = [
        ("SPX", "SPX500"), ("500", "SPX500"),
        ("BTC", "BTCUSDT"), ("ETH", "ETHUSDT"),
        ("NASDAQ", "NASDAQ100"), ("100", "NASDAQ100"),
        ("DOW", "US30"), ("US30", "US30"), ("30", "US30")
    ]
    
    for pattern, symbol in symbol_patterns:
        if pattern in message_upper:
            return symbol
    
    # Try to extract symbol from special characters
    clean_message = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', message_upper)
    
    # Look for 4-digit numbers
    number_matches = re.findall(r'\b\d{4}\b', clean_message)
    if number_matches:
        return number_matches[0]
    
    # Look for common crypto patterns
    crypto_patterns = [
        r'(\w+BTC)',
        r'(\w+ETH)',
        r'(\w+USDT)',
        r'(\w+USD)',
    ]
    
    for pattern in crypto_patterns:
        matches = re.findall(pattern, clean_message)
        if matches:
            return matches[0]
    
    # If we have a multi-line message, check each line for symbols
    lines = clean_message.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if the entire line might be a symbol
        if len(line) <= 10 and line.isalnum():
            if any(x in line for x in ['BTC', 'ETH', 'USDT', 'USD', 'SPX', 'NASDAQ', 'DOW']):
                return line
            if re.match(r'^\d{4}$', line):
                return line
    
    return "UNKNOWN"

# Improved signal name cleaning
def extract_clean_signal_name(raw_signal):
    cache_key = f"signal_{hash(raw_signal)}"
    if cache_key in signal_cache and time.time() - signal_cache[cache_key]['time'] < CACHE_TIMEOUT:
        return signal_cache[cache_key]['value']
    
    # First remove special Unicode characters
    clean_signal = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', raw_signal)
    
    # Remove technical patterns and numbers
    clean_signal = re.sub(r'_\d+\.\d+', '', clean_signal)
    clean_signal = re.sub(r'\b\d{4}\b', '', clean_signal)
    
    # Remove known symbols
    for symbol in STOCK_LIST:
        clean_signal = clean_signal.replace(symbol, '').replace(symbol.lower(), '')
    
    # Remove common patterns
    patterns_to_remove = ["SPX", "500", "BTC", "ETH", "USDT", "USD", "NASDAQ", "100", "DOW", "US30", "30"]
    for pattern in patterns_to_remove:
        clean_signal = clean_signal.replace(pattern, '').replace(pattern.lower(), '')
    
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    
    result = clean_signal if clean_signal else "Trading Signal"
    
    signal_cache[cache_key] = {'value': result, 'time': time.time()}
    return result

# Check if signal is a trend signal
def is_trend_signal(signal_text):
    signal_lower = signal_text.lower()
    trend_keywords = ["trend catcher", "trendcatcher", "market structure", "direction", "trend"]
    return any(keyword in signal_lower for keyword in trend_keywords)

# Process trend signals
def process_trend_signal(symbol, signal_text, direction):
    global last_trend_direction, last_trend_message
    
    clean_signal = extract_clean_signal_name(signal_text)
    saudi_time = get_saudi_time()
    
    # Check if trend direction changed
    if direction != last_trend_direction:
        last_trend_direction = direction
        
        if direction == "bullish":
            message = f"""📈 <b>{symbol} - تغير الاتجاه العام</b>

🎯 <b>الإشارة:</b> {clean_signal}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>الاتجاه العام أصبح صاعداً - متوقع حركة صعودية</code>"""
        else:
            message = f"""📉 <b>{symbol} - تغير الاتجاه العام</b>

🎯 <b>الإشارة:</b> {clean_signal}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>الاتجاه العام أصبح هابطاً - متوقع حركة هبوطية</code>"""
        
        telegram_success = send_telegram_to_all(message)
        external_success = send_post_request(message, "TREND_SIGNAL", 
                                           "TREND_BULLISH" if direction == "bullish" else "TREND_BEARISH")
        
        if telegram_success:
            last_trend_message = message
            print(f"🎉 Trend alert sent for {symbol} ({direction})")
        
        return True
    return False

# Process confirmation signals - معالجة الحالة عندما لا يكون هناك اتجاه عام
def process_confirmation_signals(symbol, direction):
    signals = signal_memory[symbol][direction]
    
    if len(signals) >= REQUIRED_CONFIRMATION_SIGNALS:
        saudi_time = get_saudi_time()
        signal_count = len(signals)
        
        # Get the clean signal name from the latest signal
        latest_signal, latest_ts = signals[-1]
        clean_signal = extract_clean_signal_name(latest_signal)
        
        # Check if confirmation matches current trend OR if no trend is set yet
        if (last_trend_direction is None) or \
           (direction == "bullish" and last_trend_direction == "bullish") or \
           (direction == "bearish" and last_trend_direction == "bearish"):
            
            if direction == "bullish":
                if last_trend_direction == "bullish":
                    trend_text = "مع الاتجاه العام - متوقع حركة صعودية"
                elif last_trend_direction == "bearish":
                    trend_text = "عكس الاتجاه العام - احتياط"
                else:
                    trend_text = "إشارة صعودية - مراقبة الأداء"
                
                message = f"""🚀 <b>{symbol} - تأكيد دخول صعودي</b>

🎯 <b>الإشارة التأكيدية:</b> {clean_signal}
🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>{trend_text}</code>"""
            else:
                if last_trend_direction == "bearish":
                    trend_text = "مع الاتجاه العام - متوقع حركة هبوطية"
                elif last_trend_direction == "bullish":
                    trend_text = "عكس الاتجاه العام - احتياط"
                else:
                    trend_text = "إشارة هبوطية - مراقبة الأداء"
                
                message = f"""📉 <b>{symbol} - تأكيد دخول هبوطي</b>

🎯 <b>الإشارة التأكيدية:</b> {clean_signal}
🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>{trend_text}</code>"""
            
            telegram_success = send_telegram_to_all(message)
            external_success = send_post_request(message, "CONFIRMATION_SIGNALS", 
                                               "BULLISH_CONFIRMATION" if direction == "bullish" else "BEARISH_CONFIRMATION")
            
            if telegram_success:
                print(f"🎉 Confirmation alert sent for {symbol} ({direction})")
            
            # Clear confirmation signals after sending
            signal_memory[symbol][direction] = []
            return True
    
    return False

# Optimized alert processing
def process_alerts(alerts):
    start_time = time.time()
    
    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            ticker = alert.get("ticker", "")
        else:
            signal = str(alert).strip()
            ticker = ""

        if not signal:
            continue

        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            print(f"⚠️  Could not extract symbol from: {signal}")
            continue

        signal_lower = signal.lower()
        direction = "bearish" if any(word in signal_lower for word in ["bearish", "down", "put", "short"]) else "bullish"

        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": [], "trend_bullish": False, "trend_bearish": False}
        
        # Check if it's a trend signal
        if is_trend_signal(signal):
            process_trend_signal(ticker, signal, direction)
        else:
            # Store confirmation signal
            current_signals = signal_memory[ticker][direction]
            if len(current_signals) >= MAX_SIGNALS_PER_SYMBOL:
                current_signals.pop(0)
            
            current_signals.append((signal, datetime.utcnow()))
            
            # Log stored signal
            clean_signal_name = extract_clean_signal_name(signal)
            print(f"✅ Stored {direction} confirmation signal for {ticker}: {clean_signal_name}")
            
            # Process confirmation signals
            process_confirmation_signals(ticker, direction)

    # Clean up periodically
    if random.random() < 0.3:
        cleanup_signals()

# Log incoming request information
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\n🌐 Incoming request: {request.method} {request.path}")
        print(f"🌐 Content-Type: {request.content_type}")

# Receive webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        raw_data = None

        # Log raw data
        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"📨 Received raw webhook data: '{raw_data}'")
            
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    print(f"📊 Parsed JSON data: {data}")
                    
                    if isinstance(data, dict):
                        alerts = data.get("alerts", [data])
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    
            elif raw_data:
                alerts = [{"signal": raw_data}]
                
        except Exception as parse_error:
            print(f"❌ Raw data parse error: {parse_error}")

        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                alerts = data.get("alerts", [data] if data else [])
            except Exception as json_error:
                print(f"❌ JSON parse error: {json_error}")

        if not alerts and raw_data:
            alerts = [{"signal": raw_data}]

        print(f"🔍 Processing {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "processed", "count": len(alerts)}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print(f"❌ Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

# Home page for checking
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver is active",
        "current_trend": last_trend_direction,
        "monitored_stocks": STOCK_LIST,
        "required_confirmation_signals": REQUIRED_CONFIRMATION_SIGNALS
    })

# Run the application
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Server started on port {port}")
    print(f"🟢 Telegram receiver: {CHAT_ID}")
    print(f"🟢 Required confirmation signals: {REQUIRED_CONFIRMATION_SIGNALS}")
    print("🟢 Waiting for TradingView webhooks...")
    app.run(host="0.0.0.0", port=port)
