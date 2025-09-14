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

# إعدادات التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 3
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# ذاكرة مؤقتة للإشارات المعالجة
signal_cache = {}
CACHE_TIMEOUT = 300

# الحصول على التوقيت السعودي بشكل محسن
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# إزالة علامات HTML بشكل محسن
def remove_html_tags(text):
    if not text:
        return text
    return re.sub('<.*?>', '', text)

# إرسال التلغرام بشكل محسن
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

# تحميل قائمة الأسهم بشكل محسن
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

# قائمة الأسهم
STOCK_LIST = load_stocks()

# ذاكرة الإشارات المحسنة
MAX_SIGNALS_PER_SYMBOL = 20
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": []})

# طلب POST الخارجي المحسن
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

# تنظيف الإشارات المحسن
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
        print(f"🧹 تم تنظيف {cleanup_count} إشارة قديمة")

# استخراج الرمز بشكل محسن
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

# تحسين تنظيف اسم الإشارة - إزالة رموز الأسهم والطوابع الزمنية
def extract_clean_signal_name(raw_signal):
    cache_key = f"signal_{hash(raw_signal)}"
    if cache_key in signal_cache and time.time() - signal_cache[cache_key]['time'] < CACHE_TIMEOUT:
        return signal_cache[cache_key]['value']
    
    # إزالة الطوابع الزمنية
    clean_signal = re.sub(r'_\d+\.\d+', '', raw_signal)
    
    # إزالة الأرقام
    clean_signal = re.sub(r'\b\d+\b', '', raw_signal)
    
    # إزالة رموز الأسهم من نص الإشارة
    for symbol in STOCK_LIST:
        clean_signal = clean_signal.replace(symbol, '').replace(symbol.lower(), '')
    
    # إزالة الأنماط المعروفة
    for pattern, symbol in _symbol_patterns:
        clean_signal = clean_signal.replace(pattern, '').replace(pattern.lower(), '')
    
    # إزالة الأحرف Unicode الخاصة (مثل العلامات الاتجاهية)
    clean_signal = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', clean_signal)
    
    # تنظيف المسافات الإضافية والتقليم
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    
    result = clean_signal if clean_signal else "إشارة غير معروفة"
    
    signal_cache[cache_key] = {'value': result, 'time': time.time()}
    return result

# الحصول على الإشارات الحالية للرمز والاتجاه
def get_current_signals_info(symbol, direction):
    """الحصول على معلومات منسقة عن الإشارات الحالية"""
    signals = signal_memory.get(symbol, {}).get(direction, [])
    if not signals:
        return "لا توجد إشارات حتى الآن"
    
    # الحصول على أسماء الإشارات الفريدة
    unique_signals = set()
    signal_details = []
    for sig, ts in signals:
        clean_signal = extract_clean_signal_name(sig)
        unique_signals.add(clean_signal)
        signal_details.append((clean_signal, ts))
    
    signal_count = len(signals)
    unique_count = len(unique_signals)
    
    info = f"الحالية: {signal_count} إشارة، الفريدة: {unique_count} نوع"
    
    # إضافة أسماء الإشارات مع الطوابع الزمنية إذا كانت هناك إشارات
    if unique_signals:
        info += f"\n📋 الإشارات الحالية:\n"
        for i, signal_name in enumerate(list(unique_signals)[:10], 1):
            # العثور على أول occurrence لهذه الإشارة
            first_occurrence = next((ts for sig, ts in signal_details if sig == signal_name), None)
            time_str = first_occurrence.strftime('%H:%M:%S') if first_occurrence else "غير معروف"
            info += f"   {i}. {signal_name} (منذ {time_str})\n"
    
    return info

# فحص تفرد الإشارة المحسن
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

# معالجة التنبيهات المحسنة مع تسجيل محسن
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
        
        # تسجيل كل إشارة مخزنة مع الاسم النظيف
        clean_signal_name = extract_clean_signal_name(signal)
        print(f"✅ تم تخزين إشارة {direction} لـ {ticker}: {clean_signal_name}")

    # التنظيف الدوري
    if random.random() < 0.3:
        cleanup_signals()

    # التحقق من الإشارات المطلوبة مع تسجيل محسن
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count > 0:
                # دائمًا عرض التقدم، ليس فقط عند الانتظار
                signals_info = get_current_signals_info(symbol, direction)
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
                        print(f"🎉 تم إرسال التنبيه بنجاح لـ {symbol} ({direction})")
                    
                    signal_memory[symbol][direction] = []
                    
                else:
                    print(f"⏳ في انتظار إشارات مختلفة لـ {symbol} ({direction})")
                    print(f"   {signals_info}")
                    print(f"   تحتاج {REQUIRED_SIGNALS} إشارات مختلفة، حالياً لديك {len(unique_signals)}")
                    
                    # إنهاء مبكر إذا استغرقت المعالجة وقتًا طويلاً
                    if time.time() - start_time > 2.0:
                        return

# تسجيل معلومات الطلب الوارد
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\n🌐 طلب وارد: {request.method} {request.path}")
        print(f"🌐 نوع المحتوى: {request.content_type}")

# استقبال webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        raw_data = None

        # تسجيل البيانات الخام
        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"📨 تم استقبال بيانات webhook الخام: '{raw_data}'")
            
            # محاولة تحليل JSON
            if raw_data and raw_data.startswith('{') and raw_data.endswith('}'):
                try:
                    data = json.loads(raw_data)
                    print(f"📊 بيانات JSON المحللة: {data}")
                    
                    if isinstance(data, dict):
                        if "alerts" in data:
                            alerts = data["alerts"]
                        else:
                            alerts = [data]
                    elif isinstance(data, list):
                        alerts = data
                        
                except json.JSONDecodeError as e:
                    print(f"❌ خطأ في فك تشفير JSON: {e}")
                    
            elif raw_data:
                alerts = [{"signal": raw_data, "raw_data": raw_data}]
                
        except Exception as parse_error:
            print(f"❌ خطأ في تحليل البيانات الخام: {parse_error}")

        # طريقة طلب JSON التقليدية
        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                print(f"📊 تم استقبال webhook JSON: {data}")
                alerts = data.get("alerts", [])
                if not alerts and data:
                    alerts = [data]
            except Exception as json_error:
                print(f"❌ خطأ في تحليل JSON: {json_error}")

        # إذا لم تكن هناك تنبيهات، استخدم البيانات الخام
        if not alerts and raw_data:
            alerts = [{"signal": raw_data, "raw_data": raw_data}]

        print(f"🔍 معالجة {len(alerts)} تنبيه(ات)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({
                "status": "alert_processed", 
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        else:
            print("⚠️ لم يتم العثور على تنبيهات صالحة في webhook")
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        print(f"❌ خطأ في webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

# الصفحة الرئيسية للفحص
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "مستقبل webhook الخاص بـ TradingView نشط",
        "monitored_stocks": STOCK_LIST,
        "required_signals": REQUIRED_SIGNALS,
        "active_signals": {k: v for k, v in signal_memory.items()},
        "timestamp": datetime.utcnow().isoformat()
    })

# اختبار خدمة التلغرام والخادم الخارجي
def test_services():
    print("جاري اختبار الخدمات...")
    
    # اختبار التلغرام
    telegram_result = send_telegram_to_all("🔧 رسالة اختبار من البوت - النظام يعمل!")
    print(f"نتيجة اختبار التلغرام: {telegram_result}")
    
    # اختبار الخادم الخارجي
    external_result = send_post_request("رسالة اختبار", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    print(f"نتيجة اختبار API الخارجي: {external_result}")
    
    return telegram_result and external_result

# تشغيل التطبيق
if __name__ == "__main__":
    # اختبار الخدمات أولاً
    test_services()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 تم بدء الخادم على المنفذ {port}")
    print(f"🟢 مستقبل التلغرام: {CHAT_ID}")
    print(f"🟢 الأسهم الخاضعة للمراقبة: {', '.join(STOCK_LIST)}")
    print(f"🟢 التوقيت السعودي: UTC+{TIMEZONE_OFFSET}")
    print(f"🟢 الإشارات المطلوبة: {REQUIRED_SIGNALS}")
    print(f"🟢 API الخارجي: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    print("🟢 في انتظار webhooks من TradingView...")
    app.run(host="0.0.0.0", port=port)
