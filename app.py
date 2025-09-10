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

# ✅ استخراج اسم السهم من الرسالة (معدل)
def extract_symbol(message):
    message_upper = message.upper()
    
    # البحث عن أي رمز سهم في القائمة (بترتيب عكسي للأطول أولاً لتجنب المطابقات الجزئية)
    sorted_stocks = sorted(STOCK_LIST, key=len, reverse=True)
    for symbol in sorted_stocks:
        if symbol in message_upper:
            return symbol
    
    # إذا لم يتم العثور، البحث عن patterns معروفة
    if "SPX" in message_upper or "500" in message_upper:
        return "SPX500"
    elif "BTC" in message_upper:
        return "BTCUSDT" 
    elif "ETH" in message_upper:
        return "ETHUSDT"
    elif "NASDAQ" in message_upper or "100" in message_upper:
        return "NASDAQ100"
    elif "DOW" in message_upper or "US30" in message_upper or "30" in message_upper:
        return "US30"
    
    return "SPX500"  # افتراضي

# ✅ استخراج اسم الإشارة من الرسالة (محدث لمؤشرات LuxAlgo بالإنجليزية والعربية)
def extract_signal_name(raw_signal):
    signal_lower = raw_signal.lower()
    
    # ✅ LuxAlgo HYPERTH Signals - الإشارات المتقدمة (لا يوجد ترجمة رسمية)
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
    
    # ✅ LuxAlgo Confirmation Signals - إشارات التأكيد
    confirmation_terms = [
        "bullish_confirmation", "bullish confirmation", "confirm bullish",
        "bearish_confirmation", "bearish confirmation", "confirm bearish",
        "تأكيد صعودي", "إشارة تأكيد صعودية", "تأكيد شراء",
        "تأكيد هبوطي", "إشارة تأكيد هبوطية", "تأكيد بيع"
    ]
    if any(term in signal_lower for term in confirmation_terms):
        if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد", "شراء"]):
            return "تأكيد إشارة صعودية"
        elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط", "بيع"]):
            return "تأكيد إشارة هبوطية"
    
    # ✅ LuxAlgo Contrarian Signals - إشارات انعكاسية (ضد الاتجاه)
    contrarian_terms = [
        "bullish_contrarian", "bullish contrarian", "contrarian bullish",
        "bearish_contrarian", "bearish contrarian", "contrarian bearish",
        "انعكاس صعودي", "إشارة عكسية صعودية", "ضد الاتجاه صعودي",
        "انعكاس هبوطي", "إشارة عكسية هبوطية", "ضد الاتجاه هبوطي"
    ]
    if any(term in signal_lower for term in contrarian_terms):
        if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد"]):
            return "إشارة انعكاسية صعودية"
        elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط"]):
            return "إشارة انعكاسية هبوطية"
    
    # ✅ LuxAlgo Smart Trail Signals - المؤشر الذكي للمسار
    smart_trail_terms = [
        "smart_trail", "smart trail", "المسار الذكي",
        "bullish_smart_trail", "smart trail bullish",
        "bearish_smart_trail", "smart trail bearish",
        "المسار الذكي صعودي", "المسار الصاعد",
        "المسار الذكي هبوطي", "المسار الهابط"
    ]
    if any(term in signal_lower for term in smart_trail_terms):
        if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد"]):
            return "المسار الذكي صعودي"
        elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط"]):
            return "المسار الذكي هبوطي"
    
    # ✅ LuxAlgo Reversal Zones - مناطق الانعكاس
    reversal_zones_terms = [
        "reversal_zones", "reversal zones", "مناطق الانعكاس",
        "rz_r1", "rz_r2", "rz_r3", "rz_s1", "rz_s2", "rz_s3",
        "منطقة مقاومة", "منطقة دعم", "مناطق تحول"
    ]
    if any(term in signal_lower for term in reversal_zones_terms):
        if any(term in signal_lower for term in ["bullish", "صعودي", "buy", "شراء"]):
            return "منطقة انعكاس صعودية"
        elif any(term in signal_lower for term in ["bearish", "هبوطي", "sell", "بيع"]):
            return "منطقة انعكاس هبوطية"
    
    # ✅ LuxAlgo Trend Catcher/Tracer - مؤشر تحديد الاتجاه
    trend_terms = [
        "trend_catcher", "trend catcher", "محدد الاتجاه",
        "trend_tracer", "trend tracer", "متابع الاتجاه",
        "bullish_trend", "trend bullish", "اتجاه صعودي",
        "bearish_trend", "trend bearish", "اتجاه هبوطي"
    ]
    if any(term in signal_lower for term in trend_terms):
        if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد"]):
            return "مؤشر اتجاه صعودي"
        elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط"]):
            return "مؤشر اتجاه هبوطي"
    
    # ✅ LuxAlgo Neo Cloud - السحابة المتقدمة
    neo_cloud_terms = [
        "neo_cloud", "neo cloud", "السحابة المتقدمة",
        "bullish_neo", "neo bullish", "سحابة صعودية",
        "bearish_neo", "neo bearish", "سحابة هبوطية"
    ]
    if any(term in signal_lower for term in neo_cloud_terms):
        if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد"]):
            return "السحابة المتقدمة صعودية"
        elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط"]):
            return "السحابة المتقدمة هبوطية"
    
    # ✅ LuxAlgo Oscillator Matrix - مصفوفة المذبذبات
    oscillator_terms = [
        "hyperwave", "هايبروايف", "موجة متقدمة",
        "moneyflow", "تدفق الأموال", "حركة رأس المال",
        "overflow", "فيضان", "تدفق زائد",
        "confluence", "تقارب", "تزامن الإشارات",
        "bullish_confluence", "confluence bullish", "تقارب صعودي",
        "bearish_confluence", "confluence bearish", "تقارب هبوطي"
    ]
    if any(term in signal_lower for term in oscillator_terms):
        if "confluence" in signal_lower or "تقارب" in signal_lower:
            if any(term in signal_lower for term in ["bullish", "صعودي", "strong", "قوي"]):
                return "تقارب إشارات صعودي قوي"
            elif any(term in signal_lower for term in ["bearish", "هبوطي", "strong", "قوي"]):
                return "تقارب إشارات هبوطي قوي"
            elif any(term in signal_lower for term in ["bullish", "صعودي"]):
                return "تقارب إشارات صعودي"
            elif any(term in signal_lower for term in ["bearish", "هبوطي"]):
                return "تقارب إشارات هبوطي"
        elif "hyperwave" in signal_lower or "هايبروايف" in signal_lower:
            return "إشارة موجة متقدمة"
        elif "moneyflow" in signal_lower or "تدفق" in signal_lower:
            return "إشارة تدفق الأموال"
        elif "overflow" in signal_lower or "فيضان" in signal_lower:
            return "إشارة تدفق زائد"
    
    # ✅ Price Action Concepts (BOS/CHOCH) - مفاهيم تحليل السعر
    price_action_terms = [
        "bullish bos", "bullish break of structure", "bos bullish",
        "bearish bos", "bearish break of structure", "bos bearish",
        "bullish choch", "bullish change of character", "choch bullish",
        "bearish choch", "bearish change of character", "choch bearish",
        "كسر هيكل صعودي", "كسر الهيكل الصاعد", "اختراق صعودي",
        "كسر هيكل هبوطي", "كسر الهيكل الهابط", "اختراق هبوطي",
        "تغير هيكل صعودي", "تغيير نمط صعودي", "تحول صعودي",
        "تغير هيكل هبوطي", "تغيير نمط هبوطي", "تحول هبوطي"
    ]
    if any(term in signal_lower for term in price_action_terms):
        if "bos" in signal_lower or "break" in signal_lower or "كسر" in signal_lower or "اختراق" in signal_lower:
            if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد"]):
                return "كسر هيكل صعودي"
            elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط"]):
                return "كسر هيكل هبوطي"
        elif "choch" in signal_lower or "change" in signal_lower or "تغير" in signal_lower or "تحول" in signal_lower:
            if any(term in signal_lower for term in ["bullish", "صعودي", "صاعد"]):
                return "تغير في الهيكل صعودي"
            elif any(term in signal_lower for term in ["bearish", "هبوطي", "هابط"]):
                return "تغير في الهيكل هبوطي"
    
    # ✅ Order Blocks & Liquidity - كتل الأوامر والسيولة
    advanced_terms = [
        "order_block", "order block", "كتلة أوامر",
        "liquidity", "ликвидность", "سيولة",
        "bullish ob", "ob bullish", "كتلة أوامر صعودية",
        "bearish ob", "ob bearish", "كتلة أوامر هبوطية",
        "liquidity grab", "grab liquidity", "جذب السيولة"
    ]
    if any(term in signal_lower for term in advanced_terms):
        if "order" in signal_lower or "block" in signal_lower or "كتلة" in signal_lower:
            if any(term in signal_lower for term in ["bullish", "صعودي", "buy", "شراء"]):
                return "كتلة أوامر صعودية"
            elif any(term in signal_lower for term in ["bearish", "هبوطي", "sell", "بيع"]):
                return "كتلة أوامر هبوطية"
        elif "liquidity" in signal_lower or "سيولة" in signal_lower:
            if any(term in signal_lower for term in ["bullish", "صعودي"]):
                return "جذب سيولة صعودي"
            elif any(term in signal_lower for term in ["bearish", "هبوطي"]):
                return "جذب سيولة هبوطي"
    
    # ✅ Exit Signals - إشارات الخروج
    exit_terms = [
        "exit_buy", "exit buy", "خروج شراء",
        "exit_sell", "exit sell", "خروج بيع",
        "خروج صعودي", "خروج من شراء",
        "خروج هبوطي", "خروج من بيع"
    ]
    if any(term in signal_lower for term in exit_terms):
        if any(term in signal_lower for term in ["buy", "شراء", "صعودي"]):
            return "إشارة خروج من شراء"
        elif any(term in signal_lower for term in ["sell", "بيع", "هبوطي"]):
            return "إشارة خروج من بيع"
    
    # ✅ General Signals - إشارات عامة
    if any(term in signal_lower for term in ["bullish", "long", "buy", "صعودي", "شراء", "صاعد"]):
        return "إشارة صعودية"
    elif any(term in signal_lower for term in ["bearish", "short", "sell", "هبوطي", "بيع", "هابط"]):
        return "إشارة هبوطية"
    
    # ✅ Default - الإشارة الأصلية
    return raw_signal

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

    # التحقق من إشارات كل سهم - إشارتان على الأقل (تم التغيير من 1 إلى 2)
    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:  # إشارتان على الأقل
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
                
                # إرسال إلى التليجرام (مع تنسيق HTML)
                telegram_success = send_telegram_to_all(message)
                
                # إرسال إلى الخادم الخارجي (بدون تنسيق HTML)
                external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)
                
                if telegram_success and external_success:
                    print(f"🎉 تم إرسال التنبيه بنجاح لـ {symbol}")
                elif telegram_success and not external_success:
                    print(f"⚠️ تم الإرسال للتليجرام لكن فشل الخادم الخارجي لـ {symbol}")
                else:
                    print(f"❌ فشل الإرسال بالكامل لـ {symbol}")
                
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

# 🔹 اختبار التليجرام والخادم الخارجي
def test_services():
    print("Testing services...")
    
    # اختبار التليجرام
    telegram_result = send_telegram_to_all("🔧 Test message from bot - System is working!")
    print(f"Telegram test result: {telegram_result}")
    
    # اختبار الخادم الخارجي
    external_result = send_post_request("Test message", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    print(f"External API test result: {external_result}")
    
    return telegram_result and external_result

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
