from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json

app = Flask(__name__)

# 🔹 بيانات التليجرام لمتعدد المستلمين
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9c"
CHAT_IDS = [
    "624881400",          # Chat ID الأول
    "-1001234567890",     # Chat ID الثاني (لمجموعة)
    "-1009876543210"      # Chat ID الثالث (لقناة)
]

# 🔹 إرسال رسالة لجميع الدردشات
def send_telegram_to_all(message):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload)
            print(f"تم الإرسال إلى {chat_id}: {response.status_code}")
        except Exception as e:
            print(f"خطأ أثناء الإرسال إلى {chat_id}: {e}")

# 🔹 تحميل قائمة الأسهم من ملف
def load_stocks():
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        print("⚠️  ملف stocks.txt غير موجود. سيتم استخدام قائمة افتراضية.")
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500"]  # قائمة افتراضية
    return stocks

# قائمة الأسهم
STOCK_LIST = load_stocks()

# 🔹 ذاكرة مؤقتة لتخزين الإشارات لكل سهم
signal_memory = defaultdict(lambda: {
    "bullish": [],
    "bearish": []
})

# 🔹 إرسال POST خارجي (معدل)
def send_post_request(message, indicators, signal_type=None):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    
    # تحديد نوع الإشارة تلقائياً إذا لم يتم تحديده
    if signal_type is None:
        if "صعودي" in message or "🚀" in message:
            signal_type = "BULLISH_SIGNAL"
        elif "هبوطي" in message or "📉" in message:
            signal_type = "BEARISH_SIGNAL"
        else:
            signal_type = "TRADING_SIGNAL"
    
    payload = {
        "type": signal_type,  # نوع واضح للإشارة
        "message": message,    # نص الرسالة الكامل
        "extras": {
            "indicators": indicators,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    try:
        response = requests.post(url, json=payload)
        print(f"✅ تم إرسال الطلب: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}")
        return False

# 🔹 تنظيف الإشارات القديمة (أكثر من 15 دقيقة)
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts) for sig, ts in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
        # تنظيف الذاكرة من الأسهم الفارغة
        if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
            del signal_memory[symbol]

# ✅ تحويل النص الخام إلى صياغة مرتبة
def format_signal(signal_text, direction):
    signal_lower = signal_text.lower()
    if "upward" in signal_lower or "bullish" in signal_lower or "call" in signal_lower:
        return f"🚀 {signal_text}"
    elif "downward" in signal_lower or "bearish" in signal_lower or "put" in signal_lower:
        return f"📉 {signal_text}"
    else:
        symbol = "🚀" if direction == "bullish" else "📉"
        return f"{symbol} {signal_text}"

# ✅ استخراج اسم السهم من الرسالة
def extract_symbol(message):
    message_upper = message.upper()
    for symbol in STOCK_LIST:
        if symbol in message_upper:
            return symbol
    return "UNKNOWN"

# ✅ معالجة التنبيهات مع شرط اجتماع إشارتين على الأقل
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

        # استخراج السهم إذا لم يكن موجودًا
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            print(f"⚠️ Could not extract symbol from: {signal}")
            continue

        # تحديد الاتجاه تلقائياً من الإشارة
        signal_lower = signal.lower()
        if "bearish" in signal_lower or "down" in signal_lower or "put" in signal_lower or "short" in signal_lower:
            direction = "bearish"
        else:
            direction = "bullish"

        # تخزين الإشارة
        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": []}

        unique_key = f"{signal}_{now.timestamp()}"
        signal_memory[ticker][direction].append((unique_key, now))
        print(f"✅ Stored {direction} signal for {ticker}: {signal}")

    # تنظيف الإشارات القديمة
    cleanup_signals()

    # التحقق من إشارات كل سهم
    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= 2:
                signal_count = len(signals[direction])
                if direction == "bullish":
                    message = f"🚀 {symbol} - تأكيد انطلاق صعودي ({signal_count} إشارات)"
                    signal_type = "BULLISH_CONFIRMATION"
                else:
                    message = f"📉 {symbol} - تأكيد انطلاق هبوطي ({signal_count} إشارات)"
                    signal_type = "BEARISH_CONFIRMATION"
                
                send_telegram_to_all(message)
                send_post_request(message, f"{direction.upper()} signals", signal_type)
                
                # مسح الإشارات بعد الإرسال
                signal_memory[symbol][direction] = []
                print(f"📤 Sent alert for {symbol} ({direction})")

# 🔹 تسجيل معلومات الطلب الوارد (للت Debug)
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\n🌐 Incoming request: {request.method} {request.path}")
        print(f"🌐 Content-Type: {request.content_type}")
        print(f"🌐 Headers: { {k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'cookie']} }")

# ✅ استقبال الويب هوك (محدث)
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        raw_data = None

        # تسجيل البيانات الخام
        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"📨 Received raw webhook data: '{raw_data}'")
            
            # محاولة تحليل JSON
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    print(f"📊 Parsed JSON data: {data}")
                    
                    if isinstance(data, dict):
                        if "alerts" in data:
                            alerts = data["alerts"]
                        else:
                            alerts = [data]  # معالجة ككائن مباشر
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    # الاستمرار بالمعالجة كنص عادي
                    
            elif raw_data:
                # معالجة كرسالة نصية مباشرة
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
                
        except Exception as parse_error:
            print(f"❌ Raw data parse error: {parse_error}")

        # الطريقة التقليدية لطلب JSON
        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                print(f"📊 Received JSON webhook: {data}")
                alerts = data.get("alerts", [])
                if not alerts and data:
                    alerts = [data]
            except Exception as json_error:
                print(f"❌ JSON parse error: {json_error}")

        # إذا لم يكن هناك alerts، استخدام البيانات الخام
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

# 🔹 صفحة الرئيسية للفحص
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver is active",
        "monitored_stocks": STOCK_LIST,
        "active_signals": {k: v for k, v in signal_memory.items()},
        "timestamp": datetime.utcnow().isoformat()
    })

# 🔹 تشغيل التطبيق
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Server started on port {port}")
    print(f"🟢 Telegram receivers: {len(CHAT_IDS)}")
    print(f"🟢 Monitoring stocks: {', '.join(STOCK_LIST)}")
    print("🟢 Waiting for TradingView webhooks...")
    app.run(host="0.0.0.0", port=port)
