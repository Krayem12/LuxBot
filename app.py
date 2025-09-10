from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re

app = Flask(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3  # +3 ساعات للتوقيت السعودي

# 🔹 عدد الإشارات المطلوبة (تم التغيير من 1 إلى 2)
REQUIRED_SIGNALS = 2

# 🔹 بيانات التليجرام الصحيحة
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 الحصول على التوقيت السعودي
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# 🔹 إزالة تنسيق HTML من النص
def remove_html_tags(text):
    """إزالة علامات HTML من النص"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# 🔹 إرسال رسالة لمستخدم واحد
def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # ⏰ timeout قصير لتجنب تجميد الخادم
        response = requests.post(url, json=payload, timeout=5)
        print(f"✅ تم الإرسال إلى {CHAT_ID}: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 تم إرسال الرسالة بنجاح إلى التليجرام!")
            return True
        else:
            print(f"❌ فشل إرسال الرسالة: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ timeout التليجرام: تجاوز الوقت المحدد (5 ثواني)")
        return False
    except requests.exceptions.ConnectionError:
        print("🔌 فشل الاتصال بالتليجرام")
        return False
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
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]  # قائمة افتراضية
    return stocks

# قائمة الأسهم
STOCK_LIST = load_stocks()

# 🔹 ذاكرة مؤقتة لتخزين الإشارات لكل سهم
signal_memory = defaultdict(lambda: {
    "bullish": [],
    "bearish": []
})

# 🔹 إرسال POST خارجي (معدل لإرسال رسالة بدون تنسيق HTML)
def send_post_request(message, indicators, signal_type=None):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    
    # إزالة تنسيق HTML من الرسالة
    clean_message = remove_html_tags(message)
    
    # إرسال الرسالة بدون تنسيق HTML إلى الخادم الخارجي
    payload = {
        "text": clean_message,  # الرسالة بدون تنسيق HTML
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
        
        if response.status_code == 200:
            print("🎉 تم إرسال البيانات بنجاح إلى الخادم الخارجي!")
            return True
        else:
            print(f"❌ فشل الإرسال الخارجي: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ timeout الإرسال الخارجي: تجاوز الوقت المحدد")
        return False
    except requests.exceptions.ConnectionError:
        print("🔌 فشل الاتصال بالخادم الخارجي")
        return False
    except Exception as e:
        print(f"❌ خطأ في الإرسال الخارجي: {e}")
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

# ✅ استخراج اسم السهم من الرسالة (معدل بشكل كبير)
def extract_symbol(message, original_ticker=""):
    message_upper = message.upper()
    
    # إذا كان هناك تيكر أصلي، نستخدمه أولاً
    if original_ticker and original_ticker != "UNKNOWN":
        # تنظيف التيكر الأصلي من أي رموز غير مرغوبة
        clean_ticker = re.sub(r'[^A-Z0-9]', '', original_ticker.upper())
        if clean_ticker and clean_ticker in STOCK_LIST:
            return clean_ticker
    
    # البحث عن أي رمز سهم في القائمة (بترتيب عكسي للأطول أولاً لتجنب المطابقات الجزئية)
    sorted_stocks = sorted(STOCK_LIST, key=len, reverse=True)
    for symbol in sorted_stocks:
        # استخدام regex للبحث عن الرمز ككلمة كاملة
        if re.search(r'\b' + re.escape(symbol) + r'\b', message_upper):
            return symbol
    
    # إذا لم يتم العثور، البحث عن patterns معروفة
    patterns = [
        (r'\bSPX\b.*\b500\b|\b500\b.*\bSPX\b', "SPX500"),
        (r'\bBTC\b', "BTCUSDT"),
        (r'\bETH\b', "ETHUSDT"),
        (r'\bNASDAQ\b.*\b100\b|\b100\b.*\bNASDAQ\b', "NASDAQ100"),
        (r'\bDOW\b|\bUS30\b|\b30\b', "US30"),
        (r'\bXAUUSD\b|\bGOLD\b', "XAUUSD"),
        (r'\bXAGUSD\b|\bSILVER\b', "XAGUSD"),
        (r'\bOIL\b|\bCRUDE\b', "OIL"),
    ]
    
    for pattern, symbol in patterns:
        if re.search(pattern, message_upper, re.IGNORECASE):
            return symbol
    
    return "UNKNOWN"

# ✅ استخراج اسم الإشارة من الرسالة
def extract_signal_name(raw_signal):
    signal_lower = raw_signal.lower()
    
    # ... (نفس محتوى extract_signal_name السابق)
    # LuxAlgo HYPERTH Signals
    hyperth_terms = [
        "hyperth", "hyper_th", "hypert", "هايبيرث", "هيبرث", "هيبيرث",
        "hyperth bullish", "hyperth long", "hyperth buy",
        "hyperth bearish", "hyperth short", "hyperth sell",
        "هايبيرث صعودي", "هايبيرث شراء", "هيبرث صاعد",
        "هايبيرث هبوطي", "هايبيرث بيع", "هيبرث هابط"
    ]
    
    if any(term in signal_lower for term in hyperth_terms):
        if any(term in signal_lower for term in ["bullish", "long", "buy", "صعودي", "شراء", "صاعد"]):
            return "إشارة متقدمة صعودية (HYPERTH)"
        elif any(term in signal_lower for term in ["bearish", "short", "sell", "هبوطي", "بيع", "هابط"]):
            return "إشارة متقدمة هبوطية (HYPERTH)"
        else:
            return "إشارة متقدمة (HYPERTH)"
    
    # ... (بقية إشارات LuxAlgo كما هي)
    
    return raw_signal  # الإشارة الأصلية إذا لم يتم التعرف

# ✅ معالجة التنبيهات مع شرط اجتماع إشارتين على الأقل
def process_alerts(alerts):
    now = datetime.utcnow()
    print(f"🔍 Processing {len(alerts)} alerts")

    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            direction = alert.get("direction", "").strip().lower()
            ticker = alert.get("ticker", "").strip().upper()
            # استخراج السهم من البيانات الواردة أولاً
            extracted_ticker = extract_symbol(signal, ticker)
        else:
            signal = str(alert).strip()
            direction = ""
            ticker = ""
            extracted_ticker = extract_symbol(signal)

        if extracted_ticker == "UNKNOWN":
            print(f"⚠️ Could not extract symbol from: {signal}")
            continue

        # تحديد الاتجاه تلقائياً من الإشارة إذا لم يكن محدداً
        signal_lower = signal.lower()
        if not direction:
            if any(term in signal_lower for term in ["bearish", "down", "put", "short", "هبوطي", "بيع", "هابط"]):
                direction = "bearish"
            else:
                direction = "bullish"

        # التحقق من عدم تكرار الإشارة نفسها
        if extracted_ticker not in signal_memory:
            signal_memory[extracted_ticker] = {"bullish": [], "bearish": []}

        # إنشاء مفتاح فريد للإشارة
        signal_content = re.sub(r'\s+', ' ', signal_lower)
        signal_content = re.sub(r'\b' + re.escape(extracted_ticker.lower()) + r'\b', '', signal_content)
        signal_content = signal_content.strip()
        unique_key = f"{signal_content}"
        
        # التحقق إذا كانت الإشارة مكررة في آخر 5 دقائق
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        existing_signals = [sig for sig, ts in signal_memory[extracted_ticker][direction] if ts > cutoff]
        
        if unique_key in existing_signals:
            print(f"⚠️ Ignored duplicate signal for {extracted_ticker}: '{signal}'")
            continue

        # تخزين الإشارة مع الطابع الزمني
        signal_memory[extracted_ticker][direction].append((unique_key, now))
        print(f"✅ Stored {direction} signal for {extracted_ticker}: '{signal}'")

    # تنظيف الإشارات القديمة
    cleanup_signals()

    # التحقق من إشارات كل سهم - إشارتان على الأقل
    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:
                signal_count = len(signals[direction])
                
                # استخراج اسم الإشارة من آخر إشارة مخزنة
                last_signal = signals[direction][-1][0] if signals[direction] else "إشارة"
                signal_name = extract_signal_name(last_signal)
                
                # الحصول على التوقيت السعودي
                saudi_time = get_saudi_time()
                
                if direction == "bullish":
                    message = f"""🚀 <b>{symbol} - إشارة صعودية</b>

📊 <b>نوع الإشارة:</b> {signal_name}
🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>انطلاق صعودي متوقع</code>"""
                    signal_type = "BULLISH_CONFIRMATION"
                else:
                    message = f"""📉 <b>{symbol} - إشارة هبوطية</b>

📊 <b>نوع الإشارة:</b> {signal_name}
🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>انطلاق هبوطي متوقع</code>"""
                    signal_type = "BEARISH_CONFIRMATION"
                
                # إرسال إلى التليجرام
                telegram_success = send_telegram_to_all(message)
                
                # إرسال إلى الخادم الخارجي
                external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)
                
                if telegram_success:
                    print(f"🎉 تم إرسال التنبيه بنجاح لـ {symbol}")
                else:
                    print(f"❌ فشل إرسال التنبيه لـ {symbol}")
                
                # مسح الإشارات بعد الإرسال
                signal_memory[symbol][direction] = []
                print(f"📤 Sent alert for {symbol} ({direction})")

# ... (بقية الكود كما هو بدون تغيير)

# ✅ استقبال الويب هوك
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
                            alerts = [data]
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    alerts = [{"signal": raw_data, "raw_data": raw_data}]
                    
            elif raw_data:
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
                
        except Exception as parse_error:
            print(f"❌ Raw data parse error: {parse_error}")
            alerts = [{"signal": str(parse_error), "raw_data": raw_data}]

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

# ... (بقية الكود كما هو)

# 🔹 تشغيل التطبيق
if __name__ == "__main__":
    # اختبار الخدمات أولاً
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
