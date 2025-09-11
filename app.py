from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re
import hashlib

app = Flask(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# 🔹 عدد الإشارات المطلوبة (تم التغيير إلى 2)
REQUIRED_SIGNALS = 2

# 🔹 بيانات التليجرام الصحيحة
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 وقت التكرار المسموح به (دقيقتين لمنع التكرار)
DUPLICATE_TIMEFRAME = 120  # ثانيتين

# 🔹 الحصول على التوقيت السعودي
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# 🔹 إزالة تنسيق HTML من النص
def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# 🔹 إنشاء بصمة فريدة للإشارة لمنع التكرار
def create_signal_fingerprint(signal_text, symbol, signal_type):
    content = f"{symbol}_{signal_type}_{signal_text.lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()

# 🔹 إرسال رسالة للتليجرام
def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=5)
        print(f"✅ تم الإرسال إلى {CHAT_ID}: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطأ في إرسال التليجرام: {e}")
        return False

# 🔹 تحميل قائمة الأسهم من ملف
def load_stocks():
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        print("⚠️  ملف stocks.txt غير موجود. سيتم استخدام قائمة افتراضية.")
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]
    return stocks

# قائمة الأسهم
STOCK_LIST = load_stocks()

# 🔹 ذاكرة مؤقتة لتخزين الإشارات لكل سهم
signal_memory = defaultdict(lambda: {
    "bullish": [],
    "bearish": [],
    "last_signals": {}
})

# 🔹 إرسال POST خارجي
def send_post_request(message, indicators, signal_type=None):
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
    try:
        response = requests.post(url, json=payload, timeout=5)
        print(f"✅ تم إرسال الطلب الخارجي: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطأ في الإرسال الخارجي: {e}")
        return False

# 🔹 تنظيف الإشارات القديمة
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts, fp) for sig, ts, fp in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
        current_time = datetime.utcnow()
        signal_memory[symbol]["last_signals"] = {
            fp: ts for fp, ts in signal_memory[symbol]["last_signals"].items()
            if (current_time - ts).total_seconds() < DUPLICATE_TIMEFRAME
        }
        if (not signal_memory[symbol]['bullish'] and 
            not signal_memory[symbol]['bearish'] and 
            not signal_memory[symbol]['last_signals']):
            del signal_memory[symbol]

# ✅ التحقق من التكرار
def is_duplicate_signal(symbol, signal_fingerprint):
    if symbol in signal_memory:
        last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
        if last_seen:
            time_diff = (datetime.utcnow() - last_seen).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ إشارة مكررة لـ {symbol} تم تجاهلها (الفارق: {time_diff:.1f} ثانية)")
                return True
    return False

# ✅ استخراج اسم السهم
def extract_symbol(message):
    cleaned_message = re.sub(r'[^\x00-\x7F]+', ' ', message).upper()
    sorted_stocks = sorted(STOCK_LIST, key=len, reverse=True)
    for symbol in sorted_stocks:
        if symbol in cleaned_message:
            return symbol
    if "SPX" in cleaned_message or "500" in cleaned_message:
        return "SPX500"
    elif "BTC" in cleaned_message:
        return "BTCUSDT"
    elif "ETH" in cleaned_message:
        return "ETHUSDT"
    elif "NASDAQ" in cleaned_message or "100" in cleaned_message:
        return "NASDAQ100"
    elif "DOW" in cleaned_message or "US30" in cleaned_message or "30" in cleaned_message:
        return "US30"
    return "UNKNOWN"

# ✅ استخراج نوع الإشارة الأساسي
def extract_signal_type(signal_text):
    signal_lower = signal_text.lower()
    if "confluence" in signal_lower:
        return "confluence"
    elif "bos" in signal_lower:
        return "bos"
    elif "choch" in signal_lower:
        return "choch"
    elif "overbought" in signal_lower:
        return "overbought"
    elif "oversold" in signal_lower:
        return "oversold"
    elif "bullish" in signal_lower:
        return "bullish"
    elif "bearish" in signal_lower:
        return "bearish"
    else:
        return "unknown"

# ✅ معالجة التنبيهات
def process_alerts(alerts):
    now = datetime.utcnow()
    print(f"🔍 Processing {len(alerts)} alerts")

    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            direction = alert.get("direction", "bullish").strip().lower()
            ticker = alert.get("ticker", "")
        else:
            signal = str(alert).strip()
            direction = "bullish"
            ticker = ""

        signal = re.sub(r'[^\x00-\x7F]+', ' ', signal).strip()
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)
        if ticker == "UNKNOWN":
            print(f"⚠️ Could not extract symbol from: {signal}")
            continue

        signal_lower = signal.lower()
        if ("bearish" in signal_lower or "down" in signal_lower or 
            "put" in signal_lower or "short" in signal_lower or
            "downward" in signal_lower or "overbought" in signal_lower):
            direction = "bearish"
        else:
            direction = "bullish"

        signal_type = extract_signal_type(signal)
        signal_fingerprint = create_signal_fingerprint(signal_type, ticker, direction)

        if is_duplicate_signal(ticker, signal_fingerprint):
            continue

        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": [], "last_signals": {}}
        signal_memory[ticker]["last_signals"][signal_fingerprint] = now

        unique_key = signal
        if all(sig[0] != unique_key for sig in signal_memory[ticker][direction]):
            signal_memory[ticker][direction].append((unique_key, now, signal_fingerprint))
            print(f"✅ Stored {direction} signal for {ticker}: {signal}")
        else:
            print(f"⚠️ Ignored duplicate text signal for {ticker}: {signal}")

    cleanup_signals()

    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:
                signal_count = len(signals[direction])
                saudi_time = get_saudi_time()

                unique_signals = list(dict.fromkeys([sig[0] for sig in signals[direction]]))
                signals_list = "\n".join([f"- {s}" for s in unique_signals])

                if direction == "bullish":
                    message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية</b>

📊 <b>الإشارات المستلمة:</b>
{signals_list}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

⚠️ <i>تنبيه: هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك</i>"""
                    signal_type = "BULLISH_CONFIRMATION"
                else:
                    message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية</b>

📊 <b>الإشارات المستلمة:</b>
{signals_list}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

⚠️ <i>تنبيه: هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك</i>"""
                    signal_type = "BEARISH_CONFIRMATION"

                telegram_success = send_telegram_to_all(message)
                external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)

                if telegram_success and external_success:
                    print(f"🎉 تم إرسال التنبيه بنجاح لـ {symbol}")
                elif telegram_success and not external_success:
                    print(f"⚠️ تم الإرسال للتليجرام لكن فشل الخادم الخارجي لـ {symbol}")
                else:
                    print(f"❌ فشل الإرسال بالكامل لـ {symbol}")

                signal_memory[symbol][direction] = []
                print(f"📤 Sent alert for {symbol} ({direction})")

# 🔹 تسجيل الطلبات
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\n🌐 Incoming request: {request.method} {request.path}")
        print(f"🌐 Content-Type: {request.content_type}")

# ✅ استقبال الويب هوك
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        raw_data = None
        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"📨 Received raw webhook data: '{raw_data}'")
            raw_data = re.sub(r'[^\x00-\x7F]+', ' ', raw_data).strip()
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    if isinstance(data, dict):
                        if "alerts" in data:
                            alerts = data["alerts"]
                        else:
                            alerts = [data]
                    elif isinstance(data, list):
                        alerts = data
                except json.JSONDecodeError:
                    pass
            elif raw_data:
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
        except Exception as parse_error:
            print(f"❌ Raw data parse error: {parse_error}")

        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                alerts = data.get("alerts", [])
                if not alerts and data:
                    alerts = [data]
            except Exception as json_error:
                print(f"❌ JSON parse error: {json_error}")

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
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print(f"❌ Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

# 🔹 صفحة الرئيسية
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver is active",
        "monitored_stocks": STOCK_LIST,
        "active_signals": {k: {ky: len(v) if ky in ["bullish", "bearish"] else v for ky, v in val.items()} for k, val in signal_memory.items()},
        "duplicate_timeframe": f"{DUPLICATE_TIMEFRAME} seconds",
        "required_signals": REQUIRED_SIGNALS,
        "timestamp": datetime.utcnow().isoformat()
    })

# 🔹 اختبار الخدمات
def test_services():
    print("Testing services...")
    telegram_result = send_telegram_to_all("🔧 Test message from bot - System is working!")
    external_result = send_post_request("Test message", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    return telegram_result and external_result

# 🔹 تشغيل التطبيق
if __name__ == "__main__":
    test_services()
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Server started on port {port}")
    app.run(host="0.0.0.0", port=port)
