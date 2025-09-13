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
REQUIRED_SIGNALS = 2  # يمكن تغييرها إلى 2 أو 3
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# كاش للإشارات المعالجة
signal_cache = {}
CACHE_TIMEOUT = 300

# تتبع إشارات Trend Catcher و Trend Tracer بشكل منفصل (لا يتم مسحها إلا عند تغيير الاتجاه)
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

# تحميل قائمة الأسهم
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

# ذاكرة الإشارات العادية فقط (بدون إشارات الترند)
MAX_SIGNALS_PER_SYMBOL = 20
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": []})

# إرسال طلب POST خارجي
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

# تنظيف الإشارات العادية القديمة فقط (لا تؤثر على إشارات الترند)
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
        print(f"🧹 تم تنظيف {cleanup_count} إشارة عادية قديمة")

# أنماط استخراج الرمز
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

# تنظيف اسم الإشارة
def extract_clean_signal_name(raw_signal):
    cache_key = f"signal_{hash(raw_signal)}"
    if cache_key in signal_cache and time.time() - signal_cache[cache_key]['time'] < CACHE_TIMEOUT:
        return signal_cache[cache_key]['value']
    
    clean_signal = re.sub(r'_\d+\.\d+', '', raw_signal)
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    
    for symbol in STOCK_LIST:
        clean_signal = clean_signal.replace(symbol, '').replace(symbol.lower(), '')
    
    for pattern, symbol in _symbol_patterns:
        clean_signal = clean_signal.replace(pattern, '').replace(pattern.lower(), '')
    
    clean_signal = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', clean_signal)
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    
    result = clean_signal if clean_signal else "إشارة غير معروفة"
    
    signal_cache[cache_key] = {'value': result, 'time': time.time()}
    return result

# الكشف عن إشارات الترند وتحديثها (لا تدخل في الإشارات العادية)
def check_and_update_trend_signals(signal_text, symbol):
    signal_lower = signal_text.lower()
    is_trend_signal = False
    
    # الكشف عن إشارات Trend Catcher
    if "trend catcher" in signal_lower or ("catcher" in signal_lower and "trend" in signal_lower):
        direction = "bullish" if any(word in signal_lower for word in ["bullish", "up", "call", "long", "buy"]) else "bearish"
        current_direction = trend_signals[symbol]["trend_catcher"]
        
        if current_direction is None or current_direction[0] != direction:
            trend_signals[symbol]["trend_catcher"] = (direction, datetime.utcnow())
            print(f"📊 Trend Catcher تم تحديثه إلى {direction} لـ {symbol}")
        
        is_trend_signal = True
    
    # الكشف عن إشارات Trend Tracer
    elif "trend tracer" in signal_lower or ("tracer" in signal_lower and "trend" in signal_lower):
        direction = "bullish" if any(word in signal_lower for word in ["bullish", "up", "call", "long", "buy"]) else "bearish"
        current_direction = trend_signals[symbol]["trend_tracer"]
        
        if current_direction is None or current_direction[0] != direction:
            trend_signals[symbol]["trend_tracer"] = (direction, datetime.utcnow())
            print(f"📊 Trend Tracer تم تحديثه إلى {direction} لـ {symbol}")
        
        is_trend_signal = True
    
    return is_trend_signal

# الحصول على معلومات الإشارات العادية الحالية (بدون الترند)
def get_current_signals_info(symbol, direction):
    signals = signal_memory.get(symbol, {}).get(direction, [])
    if not signals:
        return "لا توجد إشارات عادية بعد"
    
    unique_signals = set()
    for sig, ts in signals:
        clean_signal = extract_clean_signal_name(sig)
        unique_signals.add(clean_signal)
    
    signal_count = len(signals)
    unique_count = len(unique_signals)
    
    return f"الإشارات العادية: {signal_count} إشارة، الفريدة: {unique_count} نوع"

# التحقق من وجود إشارات عادية مختلفة مطلوبة (بدون الترند)
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

# التحقق من محاذاة إشارات الترند مع الاتجاه الحالي
def check_trend_alignment(symbol, direction):
    """التحقق مما إذا كانت إشارات الترند تتماشى مع اتجاه الإشارات العادية"""
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    # إذا لم تكن هناك إشارات ترند على الإطلاق
    if trend_catcher is None and trend_tracer is None:
        print(f"⚠️ لا توجد إشارات ترند لـ {symbol}")
        return False
    
    # إذا كانت هناك إشارة Trend Catcher وتتماشى مع الاتجاه
    if trend_catcher and trend_catcher[0] == direction:
        print(f"✅ Trend Catcher متوافق مع {direction} لـ {symbol}")
        return True
    
    # إذا كانت هناك إشارة Trend Tracer وتتماشى مع الاتجاه
    if trend_tracer and trend_tracer[0] == direction:
        print(f"✅ Trend Tracer متوافق مع {direction} لـ {symbol}")
        return True
    
    print(f"❌ إشارات الترند غير متوافقة مع {direction} لـ {symbol}")
    return False

# الحصول على حالة إشارات الترند الحالية
def get_trend_status(symbol):
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    status = []
    if trend_catcher:
        time_str = convert_to_saudi_time(trend_catcher[1])
        direction_emoji = "📈" if trend_catcher[0] == "bullish" else "📉"
        status.append(f"{direction_emoji} Trend Catcher: {trend_catcher[0]} (منذ {time_str})")
    else:
        status.append("❓ Trend Catcher: غير متوفر")
    
    if trend_tracer:
        time_str = convert_to_saudi_time(trend_tracer[1])
        direction_emoji = "📈" if trend_tracer[0] == "bullish" else "📉"
        status.append(f"{direction_emoji} Trend Tracer: {trend_tracer[0]} (منذ {time_str})")
    else:
        status.append("❓ Trend Tracer: غير متوفر")
    
    return "\n".join(status)

# معالجة التنبيهات
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

        # التحقق من إشارات الترند أولاً (لا تدخل في الإشارات العادية)
        is_trend_signal = check_and_update_trend_signals(signal, ticker)
        
        # معالجة الإشارات العادية فقط (ليست إشارات ترند)
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
            print(f"✅ تم تخزين إشارة عادية {direction} لـ {ticker}: {clean_signal_name} (في {saudi_time} KSA)")
        else:
            print(f"📊 تم معالجة إشارة ترند لـ {ticker} (لا تحتسب في الإشارات العادية)")

    # تنظيف الإشارات العادية القديمة فقط
    if random.random() < 0.3:
        cleanup_signals()

    # التحقق من إمكانية إرسال تنبيهات
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count > 0:
                signals_info = get_current_signals_info(symbol, direction)
                has_required, unique_signals = has_required_different_signals(signals[direction])
                
                # التحقق من محاذاة إشارات الترند مع الاتجاه الحالي
                trend_aligned = check_trend_alignment(symbol, direction)
                
                if has_required and trend_aligned:
                    saudi_time = get_saudi_time()
                    trend_status = get_trend_status(symbol)
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد دخول صفقة شراء</b>

📊 <b>الإشارات المؤكدة ({len(unique_signals)}):</b>
{chr(10).join([f'• {signal}' for signal in unique_signals[:REQUIRED_SIGNALS]])}

🎯 <b>حالة إشارات الترند:</b>
{trend_status}

🔢 <b>عدد الإشارات العادية:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد دخول صفقة شراء - إشارات الترند متوافقة مع الإشارات العادية</code>"""
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد دخول صفقة بيع</b>

📊 <b>الإشارات المؤكدة ({len(unique_signals)}):</b>
{chr(10).join([f'• {signal}' for signal in unique_signals[:REQUIRED_SIGNALS]])}

🎯 <b>حالة إشارات الترند:</b>
{trend_status}

🔢 <b>عدد الإشارات العادية:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد دخول صفقة بيع - إشارات الترند متوافقة مع الإشارات العادية</code>"""
                    
                    telegram_success = send_telegram_to_all(message)
                    external_success = send_post_request(message, f"{direction.upper()} signals", 
                                                       "BUY_CONFIRMATION" if direction == "bullish" else "SELL_CONFIRMATION")
                    
                    if telegram_success:
                        print(f"🎉 تم إرسال تنبيه دخول صفقة لـ {symbol} ({direction})")
                        # مسح الإشارات العادية فقط، إشارات الترند تبقى
                        signal_memory[symbol][direction] = []
                    
                else:
                    print(f"⏳ في انتظار شروط التنبيه لـ {symbol} ({direction})")
                    print(f"   {signals_info}")
                    print(f"   تحتاج {REQUIRED_SIGNALS} إشارات عادية مختلفة، حالياً لديك {len(unique_signals)}")
                    print(f"   {get_trend_status(symbol)}")
                    
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
                    print(f"❌ خطأ في تحليل JSON: {e}")
                    
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
        "message": "TradingView Webhook Receiver is active",
        "monitored_stocks": STOCK_LIST,
        "required_signals": REQUIRED_SIGNALS,
        "active_signals": {k: v for k, v in signal_memory.items()},
        "trend_signals": {k: v for k, v in trend_signals.items()},
        "timestamp": datetime.utcnow().isoformat()
    })

# اختبار التليجرام والخادم الخارجي
def test_services():
    print("جاري اختبار الخدمات...")
    
    # اختبار التليجرام
    telegram_result = send_telegram_to_all("🔧 رسالة اختبار من البوت - النظام يعمل!")
    print(f"نتيجة اختبار التليجرام: {telegram_result}")
    
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
    print(f"🟢 مستقبل التليجرام: {CHAT_ID}")
    print(f"🟢 الأسهم المراقبة: {', '.join(STOCK_LIST)}")
    print(f"🟢 التوقيت السعودي: UTC+{TIMEZONE_OFFSET}")
    print(f"🟢 الإشارات العادية المطلوبة: {REQUIRED_SIGNALS}")
    print(f"🟢 إشارات الترند: Trend Catcher & Trend Tracer (لا تحتسب في العد)")
    print(f"🟢 API الخارجي: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    print("🟢 في انتظار webhooks من TradingView...")
    app.run(host="0.0.0.0", port=port)
