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
REQUIRED_SIGNALS = 2  # Changed to 2 for testing
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

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
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": []})

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

# Optimized symbol extraction
_symbol_patterns = [
    ("SPX", "SPX500"), ("500", "SPX500"),
    ("BTC", "BTCUSDT"), ("ETH", "ETHUSDT"),
    ("NASDAQ", "NASDAQ100"), ("100", "NASDAQ100"),
    ("DOW", "US30"), ("US30", "US30"), ("30", "US30")
]

def extract_symbol(message):
    message_upper = message.upper()
    
    for symbol in STOCK_LIST:
        if symbol in message_upper:
            return symbol
    
    for pattern, symbol in _symbol_patterns:
        if pattern in message_upper:
            return symbol
    
    return "UNKNOWN"

# Optimized signal name cleaning - CORRECTED FUNCTION NAME
def extract_clean_signal_name(raw_signal):
    cache_key = f"signal_{hash(raw_signal)}"
    if cache_key in signal_cache and time.time() - signal_cache[cache_key]['time'] < CACHE_TIMEOUT:
        return signal_cache[cache_key]['value']
    
    clean_signal = re.sub(r'_\d+\.\d+', '', raw_signal)
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    result = clean_signal if clean_signal else "Unknown Signal"
    
    signal_cache[cache_key] = {'value': result, 'time': time.time()}
    return result

# Get current signals for a symbol and direction
def get_current_signals_info(symbol, direction):
    """Get formatted information about current signals"""
    signals = signal_memory.get(symbol, {}).get(direction, [])
    if not signals:
        return "No signals yet"
    
    # Get unique signal names
    unique_signals = set()
    for sig, ts in signals:
        clean_signal = extract_clean_signal_name(sig)
        unique_signals.add(clean_signal)
    
    signal_count = len(signals)
    unique_count = len(unique_signals)
    
    info = f"Current: {signal_count} signals, Unique: {unique_count} types"
    
    # Add signal names if there are signals
    if unique_signals:
        info += f"\n📋 Current signals:\n"
        for i, signal_name in enumerate(list(unique_signals)[:10], 1):
            info += f"   {i}. {signal_name}\n"
    
    return info

# Optimized signal uniqueness check - CORRECTED FUNCTION NAME
def has_required_different_signals(signals_list):
    if len(signals_list) < REQUIRED_SIGNALS:
        return False, []
    
    unique_signals = set()
    for sig, ts in signals_list:
        clean_signal = extract_clean_signal_name(sig)  # CORRECTED: extract_clean_signal_name
        unique_signals.add(clean_signal)
        if len(unique_signals) >= REQUIRED_SIGNALS:
            return True, list(unique_signals)
    
    return False, list(unique_signals)

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
            continue

        signal_lower = signal.lower()
        direction = "bearish" if any(word in signal_lower for word in ["bearish", "down", "put", "short"]) else "bullish"

        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": []}
        
        current_signals = signal_memory[ticker][direction]
        if len(current_signals) >= MAX_SIGNALS_PER_SYMBOL:
            current_signals.pop(0)
        
        current_signals.append((signal, datetime.utcnow()))
        print(f"✅ Stored {direction} signal for {ticker}: {signal}")

    # Clean up periodically
    if random.random() < 0.3:
        cleanup_signals()

    # Check for required signals with improved logging
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count >= REQUIRED_SIGNALS:
                has_required, unique_signals = has_required_different_signals(signals[direction])
                
                if has_required:
                    saudi_time = get_saudi_time()
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية قوية</b>

📊 <b>الإشارات المختلفة:</b>
{chr(10).join([f'• {signal}' for signal in unique_signals[:REQUIRED_SIGNALS]])}

🔢 <b>عدد الإشارات الكلي:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد صعودي قوي من {REQUIRED_SIGNALS} إشارات مختلفة - متوقع حركة صعودية</code>"""
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية قوية</b>

📊 <b>الإشارات المختلفة:</b>
{chr(10).join([f'• {signal}' for signal in unique_signals[:REQUIRED_SIGNALS]])}

🔢 <b>عدد الإشارات الكلي:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد هبوطي قوي من {REQUIRED_SIGNALS} إشارات مختلفة - متوقع حركة هبوطية</code>"""
                    
                    telegram_success = send_telegram_to_all(message)
                    external_success = send_post_request(message, f"{direction.upper()} signals", 
                                                       "BULLISH_CONFIRMATION" if direction == "bullish" else "BEARISH_CONFIRMATION")
                    
                    if telegram_success:
                        print(f"🎉 Alert sent successfully for {symbol} ({direction})")
                    
                    signal_memory[symbol][direction] = []
                    
                else:
                    # Show detailed information about current signals
                    signals_info = get_current_signals_info(symbol, direction)
                    print(f"⏳ Waiting for different signals for {symbol} ({direction})")
                    print(f"   {signals_info}")
                    print(f"   Need {REQUIRED_SIGNALS} different signals, currently have {len(unique_signals)}")
                    
                    # Break early if processing taking too long
                    if time.time() - start_time > 2.0:
                        return
            else:
                # Show progress for symbols that don't have enough signals yet
                signals_info = get_current_signals_info(symbol, direction)
                if signals_info != "No signals yet":
                    print(f"📊 Progress for {symbol} ({direction}): {signal_count}/{REQUIRED_SIGNALS} signals")
                    print(f"   {signals_info}")

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
            
            # Try to parse JSON
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    print(f"📊 Parsed JSON data: {data}")
                    
                    if isinstance(data, dict):
                        if "alerts" in data:
                            alerts = data["alerts"]
                        else:
                            alerts = [data]
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    
            elif raw_data:
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
                
        except Exception as parse_error:
            print(f"❌ Raw data parse error: {parse_error}")

        # Traditional JSON request method
        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                print(f"📊 Received JSON webhook: {data}")
                alerts = data.get("alerts", [])
                if not alerts and data:
                    alerts = [data]
            except Exception as json_error:
                print(f"❌ JSON parse error: {json_error}")

        # If no alerts, use raw data
        if not alerts and raw_data:
            alerts = [{"signal": raw_data, "raw_data": raw_data}]

        print(f"🔍 Processing {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({
                "status": "alert_processed", 
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        else:
            print("⚠️ No valid alerts found in webhook")
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
        "monitored_stocks": STOCK_LIST,
        "required_signals": REQUIRED_SIGNALS,
        "active_signals": {k: v for k, v in signal_memory.items()},
        "timestamp": datetime.utcnow().isoformat()
    })

# Test Telegram and external server
def test_services():
    print("Testing services...")
    
    # Test Telegram
    telegram_result = send_telegram_to_all("🔧 Test message from bot - System is working!")
    print(f"Telegram test result: {telegram_result}")
    
    # Test external server
    external_result = send_post_request("Test message", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    print(f"External API test result: {external_result}")
    
    return telegram_result and external_result

# Run the application
if __name__ == "__main__":
    # Test services first
    test_services()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Server started on port {port}")
    print(f"🟢 Telegram receiver: {CHAT_ID}")
    print(f"🟢 Monitoring stocks: {', '.join(STOCK_LIST)}")
    print(f"🟢 Saudi Timezone: UTC+{TIMEZONE_OFFSET}")
    print(f"🟢 Required signals: {REQUIRED_SIGNALS}")
    print(f"🟢 External API: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    print("🟢 Waiting for TradingView webhooks...")
    app.run(host="0.0.0.0", port=port)
