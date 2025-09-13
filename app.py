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

# Settings (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 2
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# Control flags - Trend enabled, Regular disabled
TREND_SIGNALS_ENABLED = True
REGULAR_SIGNALS_ENABLED = False
TEST_MODE = False

# Cache for processed signals
signal_cache = {}
CACHE_TIMEOUT = 300

# Track Trend signals
trend_signals = defaultdict(lambda: {"trend_catcher": None, "trend_tracer": None})

# Get Saudi time
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# Convert UTC to Saudi time
def convert_to_saudi_time(utc_time):
    if isinstance(utc_time, datetime):
        return (utc_time + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')
    return "Unknown"

# Remove HTML tags
def remove_html_tags(text):
    if not text:
        return text
    return re.sub('<.*?>', '', text)

# Send Telegram message
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

# Send control message to Telegram
def send_control_message(message):
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

# Stock list
STOCK_LIST = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]

# Memory for regular signals
MAX_SIGNALS_PER_SYMBOL = 20
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": []})

# Clean up old signals
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts) for sig, ts in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
            if len(signal_memory[symbol][direction]) > MAX_SIGNALS_PER_SYMBOL:
                signal_memory[symbol][direction] = signal_memory[symbol][direction][-MAX_SIGNALS_PER_SYMBOL:]
            if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
                del signal_memory[symbol]

def extract_symbol(message):
    message_upper = message.upper()
    for symbol in STOCK_LIST:
        if symbol in message_upper:
            return symbol
    return "UNKNOWN"

def extract_clean_signal_name(raw_signal):
    clean_signal = re.sub(r'_\d+\.\d+', '', raw_signal)
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    for symbol in STOCK_LIST:
        clean_signal = clean_signal.replace(symbol, '').replace(symbol.lower(), '')
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    return clean_signal if clean_signal else "Unknown Signal"

# Detect Trend signals Bullish Turn + and Bearish Turn +
def check_and_update_trend_signals(signal_text, symbol):
    if not TREND_SIGNALS_ENABLED:
        return False
        
    signal_upper = signal_text.upper()
    is_trend_signal = False
    
    # Detect Bullish Turn +
    if "BULLISH TURN +" in signal_upper:
        trend_signals[symbol]["trend_catcher"] = ("bullish", datetime.utcnow())
        print(f"📊 Trend Catcher: bullish for {symbol} (Bullish Turn +)")
        is_trend_signal = True
    
    # Detect Bearish Turn +
    elif "BEARISH TURN +" in signal_upper:
        trend_signals[symbol]["trend_catcher"] = ("bearish", datetime.utcnow())
        print(f"📊 Trend Catcher: bearish for {symbol} (Bearish Turn +)")
        is_trend_signal = True
    
    # Detect other trend signals
    elif "TURN +" in signal_upper:
        if "BULLISH" in signal_upper:
            trend_signals[symbol]["trend_catcher"] = ("bullish", datetime.utcnow())
            print(f"📊 Trend Catcher: bullish for {symbol}")
            is_trend_signal = True
        elif "BEARISH" in signal_upper:
            trend_signals[symbol]["trend_catcher"] = ("bearish", datetime.utcnow())
            print(f"📊 Trend Catcher: bearish for {symbol}")
            is_trend_signal = True
    
    # Detect Trend Tracer signals
    signal_lower = signal_text.lower()
    if 'tracer' in signal_lower:
        if any(word in signal_lower for word in ["bullish", "up", "call", "long", "buy"]):
            trend_signals[symbol]["trend_tracer"] = ("bullish", datetime.utcnow())
            print(f"📊 Trend Tracer: bullish for {symbol}")
            is_trend_signal = True
        elif any(word in signal_lower for word in ["bearish", "down", "put", "short", "sell"]):
            trend_signals[symbol]["trend_tracer"] = ("bearish", datetime.utcnow())
            print(f"📊 Trend Tracer: bearish for {symbol}")
            is_trend_signal = True
    
    return is_trend_signal

def has_required_different_signals(signals_list):
    if len(signals_list) < REQUIRED_SIGNALS:
        return False, []
    
    unique_signals = set()
    for sig, ts in signals_list:
        clean_signal = extract_clean_signal_name(sig)
        unique_signals.add(clean_signal)
        if len(unique_signals) >= REQUIRED_SIGNALS:
            return True, list(unique_signals)
    
    return False, list(unique_signals)

def check_trend_alignment(symbol, direction):
    if not TREND_SIGNALS_ENABLED:
        return True
        
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    if trend_catcher and trend_catcher[0] == direction:
        print(f"✅ Trend Catcher aligned with {direction} for {symbol}")
        return True
    
    if trend_tracer and trend_tracer[0] == direction:
        print(f"✅ Trend Tracer aligned with {direction} for {symbol}")
        return True
    
    print(f"❌ Trend signals not aligned with {direction} for {symbol}")
    return False

def get_trend_status(symbol):
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    status = []
    if trend_catcher:
        time_str = convert_to_saudi_time(trend_catcher[1])
        direction_emoji = "📈" if trend_catcher[0] == "bullish" else "📉"
        status.append(f"{direction_emoji} Trend Catcher: {trend_catcher[0]} (since {time_str})")
    else:
        status.append("❓ Trend Catcher: Not available")
    
    if trend_tracer:
        time_str = convert_to_saudi_time(trend_tracer[1])
        direction_emoji = "📈" if trend_tracer[0] == "bullish" else "📉"
        status.append(f"{direction_emoji} Trend Tracer: {trend_tracer[0]} (since {time_str})")
    else:
        status.append("❓ Trend Tracer: Not available")
    
    return "\n".join(status)

# Process control commands
def process_control_command(command):
    global TREND_SIGNALS_ENABLED, REGULAR_SIGNALS_ENABLED, TEST_MODE
    
    command_lower = command.lower().strip()
    
    if command_lower == "trend true":
        TREND_SIGNALS_ENABLED = True
        return "✅ Trend signals enabled"
    
    elif command_lower == "trend false":
        TREND_SIGNALS_ENABLED = False
        return "❌ Trend signals disabled"
    
    elif command_lower == "regular true":
        REGULAR_SIGNALS_ENABLED = True
        return "✅ Regular signals enabled"
    
    elif command_lower == "regular false":
        REGULAR_SIGNALS_ENABLED = False
        return "❌ Regular signals disabled"
    
    elif command_lower == "test true":
        TEST_MODE = True
        return "✅ Test mode enabled"
    
    elif command_lower == "test false":
        TEST_MODE = False
        return "❌ Test mode disabled"
    
    elif command_lower == "status":
        status_msg = f"""📊 <b>Current Status:</b>

🎯 <b>Trend Signals:</b> {'✅ ENABLED' if TREND_SIGNALS_ENABLED else '❌ DISABLED'}
📈 <b>Regular Signals:</b> {'✅ ENABLED' if REGULAR_SIGNALS_ENABLED else '❌ DISABLED'}
🧪 <b>Test Mode:</b> {'✅ ENABLED' if TEST_MODE else '❌ DISABLED'}

⚙️ <b>Available Commands:</b>
• trend true/false
• regular true/false  
• test true/false
• status"""
        return status_msg
    
    return "❓ Unknown command. Available: trend true/false, regular true/false, test true/false, status"

def process_alerts(alerts):
    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            ticker = alert.get("ticker", "")
        else:
            signal = str(alert).strip()
            ticker = ""

        if not signal:
            continue

        # Check if it's a control command
        if signal.lower().startswith(('trend ', 'regular ', 'test ', 'status')):
            result = process_control_command(signal)
            send_control_message(result)
            print(f"🔧 Control command processed: {signal}")
            continue

        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            continue

        print(f"📩 Incoming signal: {signal}")

        is_trend_signal = check_and_update_trend_signals(signal, ticker)
        
        if not is_trend_signal and REGULAR_SIGNALS_ENABLED:
            signal_lower = signal.lower()
            direction = "bearish" if any(word in signal_lower for word in ["bearish", "down", "put", "short", "sell"]) else "bullish"

            if ticker not in signal_memory:
                signal_memory[ticker] = {"bullish": [], "bearish": []}
            
            current_signals = signal_memory[ticker][direction]
            if len(current_signals) >= MAX_SIGNALS_PER_SYMBOL:
                current_signals.pop(0)
            
            current_time = datetime.utcnow()
            current_signals.append((signal, current_time))
            
            clean_signal_name = extract_clean_signal_name(signal)
            saudi_time = convert_to_saudi_time(current_time)
            print(f"✅ Regular {direction} signal for {ticker}: {clean_signal_name} (at {saudi_time})")
        elif is_trend_signal:
            print(f"📊 Processed trend signal for {ticker}")
        else:
            print(f"⏸️ Regular signals disabled - ignoring signal for {ticker}")

    if random.random() < 0.3:
        cleanup_signals()

    if not REGULAR_SIGNALS_ENABLED:
        return  # Skip signal processing if regular signals are disabled

    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count > 0:
                has_required, unique_signals = has_required_different_signals(signals[direction])
                trend_aligned = check_trend_alignment(symbol, direction)
                
                if has_required and (trend_aligned or TEST_MODE):
                    saudi_time = get_saudi_time()
                    trend_status = get_trend_status(symbol)
                    
                    # Telegram messages in Arabic
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد دخول صفقة شراء</b>

📊 <b>الإشارات المؤكدة ({len(unique_signals)}):</b>
{chr(10).join([f'• {signal}' for signal in unique_signals])}

🎯 <b>حالة إشارات الترند:</b>
{trend_status}

🔢 <b>عدد الإشارات العادية:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد دخول صفقة شراء - {'إشارات الترند متوافقة' if trend_aligned else 'وضع الاختبار'}</code>"""
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد دخول صفقة بيع</b>

📊 <b>الإشارات المؤكدة ({len(unique_signals)}):</b>
{chr(10).join([f'• {signal}' for signal in unique_signals])}

🎯 <b>حالة إشارات الترند:</b>
{trend_status}

🔢 <b>عدد الإشارات العادية:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد دخول صفقة بيع - {'إشارات الترند متوافقة' if trend_aligned else 'وضع الاختبار'}</code>"""
                    
                    telegram_success = send_telegram_to_all(message)
                    if telegram_success:
                        print(f"🎉 Alert sent for {symbol} ({direction})")
                        signal_memory[symbol][direction] = []
                else:
                    print(f"⏳ Waiting for conditions for {symbol} ({direction})")
                    print(f"   Need {REQUIRED_SIGNALS} different regular signals, currently have {len(unique_signals)}")
                    print(f"   {get_trend_status(symbol)}")

@app.before_request
def log_requests():
    print(f"📨 Request: {request.method} {request.path}")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST, GET')
    return response

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    try:
        if request.method == "GET":
            return jsonify({"status": "ready", "message": "Webhook endpoint is active"})
        
        alerts = []
        content_type = request.content_type or ""
        
        if 'json' in content_type:
            try:
                data = request.get_json(force=True)
                if isinstance(data, dict):
                    alerts = [data]
                elif isinstance(data, list):
                    alerts = data
            except:
                pass
        
        if not alerts:
            raw_data = request.get_data(as_text=True).strip()
            if raw_data:
                alerts = [{"signal": raw_data}]
        
        print(f"🔍 Processing {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "processed", "count": len(alerts)})
        else:
            return jsonify({"status": "no_alerts"})
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route("/control", methods=["POST", "GET"])
def control():
    """Endpoint for control commands"""
    try:
        if request.method == "GET":
            return jsonify({
                "trend_signals_enabled": TREND_SIGNALS_ENABLED,
                "regular_signals_enabled": REGULAR_SIGNALS_ENABLED,
                "test_mode": TEST_MODE
            })
        
        command = request.get_data(as_text=True).strip()
        if command:
            result = process_control_command(command)
            return jsonify({"status": "processed", "result": result})
        else:
            return jsonify({"status": "error", "message": "No command provided"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver",
        "monitored_stocks": STOCK_LIST,
        "required_signals": REQUIRED_SIGNALS,
        "trend_signals_enabled": TREND_SIGNALS_ENABLED,
        "regular_signals_enabled": REGULAR_SIGNALS_ENABLED,
        "test_mode": TEST_MODE,
        "control_commands": [
            "trend true/false - Enable/disable trend signals",
            "regular true/false - Enable/disable regular signals", 
            "test true/false - Enable/disable test mode",
            "status - Show current status"
        ]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Starting server on port {port}")
    print(f"🟢 Trend signals: {'ENABLED' if TREND_SIGNALS_ENABLED else 'DISABLED'}")
    print(f"🟢 Regular signals: {'ENABLED' if REGULAR_SIGNALS_ENABLED else 'DISABLED'}")
    print(f"🟢 Test mode: {'ENABLED' if TEST_MODE else 'DISABLED'}")
    print("🟢 Control commands: trend true/false, regular true/false, test true/false, status")
    print("🟢 Ready to receive webhooks...")
    app.run(host="0.0.0.0", port=port, debug=False)
