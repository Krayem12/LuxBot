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

# إعدادات الوقت السعودي (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 2
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"
TEST_MODE = True  # True للاختبار بدون إشارات ترند

# كاش للإشارات المعالجة
signal_cache = {}
CACHE_TIMEOUT = 300

# تتبع إشارات Trend
trend_signals = defaultdict(lambda: {"trend_catcher": None, "trend_tracer": None})

# الحصول على الوقت السعودي
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# تحويل الوقت UTC إلى الوقت السعودي
def convert_to_saudi_time(utc_time):
    if isinstance(utc_time, datetime):
        return (utc_time + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')
    return "غير معروف"

# إزالة وسوم HTML
def remove_html_tags(text):
    if not text:
        return text
    return re.sub('<.*?>', '', text)

# إرسال رسالة التليجرام
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

# قائمة الأسهم
STOCK_LIST = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]

# ذاكرة الإشارات العادية
MAX_SIGNALS_PER_SYMBOL = 20
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": []})

# تنظيف الإشارات العادية
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
    return clean_signal if clean_signal else "إشارة غير معروفة"

def check_and_update_trend_signals(signal_text, symbol):
    signal_lower = signal_text.lower()
    is_trend_signal = False
    
    if 'trend' in signal_lower or 'catcher' in signal_lower or 'tracer' in signal_lower:
        if any(word in signal_lower for word in ["bullish", "up", "call", "long", "buy"]):
            direction = "bullish"
        elif any(word in signal_lower for word in ["bearish", "down", "put", "short", "sell"]):
            direction = "bearish"
        else:
            return True
        
        if 'catcher' in signal_lower:
            trend_signals[symbol]["trend_catcher"] = (direction, datetime.utcnow())
            print(f"📊 Trend Catcher: {direction} لـ {symbol}")
            is_trend_signal = True
        elif 'tracer' in signal_lower:
            trend_signals[symbol]["trend_tracer"] = (direction, datetime.utcnow())
            print(f"📊 Trend Tracer: {direction} لـ {symbol}")
            is_trend_signal = True
        else:
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
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    if trend_catcher and trend_catcher[0] == direction:
        return True
    if trend_tracer and trend_tracer[0] == direction:
        return True
    
    return False

def get_trend_status(symbol):
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    status = []
    if trend_catcher:
        time_str = convert_to_saudi_time(trend_catcher[1])
        status.append(f"Trend Catcher: {trend_catcher[0]} (منذ {time_str})")
    else:
        status.append("Trend Catcher: غير متوفر")
    
    if trend_tracer:
        time_str = convert_to_saudi_time(trend_tracer[1])
        status.append(f"Trend Tracer: {trend_tracer[0]} (منذ {time_str})")
    else:
        status.append("Trend Tracer: غير متوفر")
    
    return "\n".join(status)

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

        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            continue

        is_trend_signal = check_and_update_trend_signals(signal, ticker)
        
        if not is_trend_signal:
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
            print(f"✅ إشارة عادية {direction} لـ {ticker}: {clean_signal_name} (في {saudi_time})")

    if random.random() < 0.3:
        cleanup_signals()

    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count > 0:
                has_required, unique_signals = has_required_different_signals(signals[direction])
                trend_aligned = check_trend_alignment(symbol, direction)
                
                if has_required and (trend_aligned or TEST_MODE):
                    saudi_time = get_saudi_time()
                    trend_status = get_trend_status(symbol)
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد دخول صفقة شراء</b>

📊 <b>الإشارات المؤكدة:</b>
{chr(10).join([f'• {signal}' for signal in unique_signals])}

🎯 <b>حالة إشارات الترند:</b>
{trend_status}

⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد دخول صفقة شراء</code>"""
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد دخول صفقة بيع</b>

📊 <b>الإشارات المؤكدة:</b>
{chr(10).join([f'• {signal}' for signal in unique_signals])}

🎯 <b>حالة إشارات الترند:</b>
{trend_status}

⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد دخول صفقة بيع</code>"""
                    
                    telegram_success = send_telegram_to_all(message)
                    if telegram_success:
                        print(f"🎉 تم إرسال تنبيه لـ {symbol} ({direction})")
                        signal_memory[symbol][direction] = []
                else:
                    print(f"⏳ في انتظار شروط التنبيه لـ {symbol} ({direction})")

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
        
        print(f"🔍 معالجة {len(alerts)} تنبيه(ات)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "processed", "count": len(alerts)})
        else:
            return jsonify({"status": "no_alerts"})
            
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver",
        "monitored_stocks": STOCK_LIST,
        "required_signals": REQUIRED_SIGNALS,
        "test_mode": TEST_MODE
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 بدء الخادم على البورت {port}")
    print(f"🟢 وضع الاختبار: {TEST_MODE}")
    print("🟢 جاهز لاستقبال webhooks...")
    app.run(host="0.0.0.0", port=port, debug=False)
