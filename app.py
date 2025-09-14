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
REQUIRED_SIGNALS = 2
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# نظام الترقيم التسلسلي للإشارات
signal_counter = 1
signal_mapping = {}  # لتخزين mapping بين الرقم والإشارة

# ذاكرة للإشارات المكررة وتوقيت التصفير
duplicate_signals = set()
last_signal_time = datetime.utcnow()
RESET_TIMEOUT = 900  # 15 دقيقة بالثواني

# ذاكرة مؤقتة للطلبات
request_cache = {}
CACHE_DURATION = 30  # ثانية

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

# توليد رقم تسلسلي فريد لكل إشارة
def generate_signal_id(signal_text):
    global signal_counter
    signal_id = signal_counter
    signal_counter += 1
    signal_mapping[signal_id] = signal_text
    return signal_id

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
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30", "XAUUSD", "XAGUSD", "USOIL"]
    
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
    global duplicate_signals
    
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    cleanup_count = 0
    
    # تنظيف الإشارات المكررة القديمة
    if duplicate_signals:
        print(f"🧹 تنظيف ذاكرة الإشارات المكررة: {len(duplicate_signals)} إشارة")
        duplicate_signals.clear()
    
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            original_count = len(signal_memory[symbol][direction])
            signal_memory[symbol][direction] = [
                (sig, ts, signal_id) for sig, ts, signal_id in signal_memory[symbol][direction] 
                if ts > cutoff
            ]
            cleanup_count += (original_count - len(signal_memory[symbol][direction]))
            
            if len(signal_memory[symbol][direction]) > MAX_SIGNALS_PER_SYMBOL:
                signal_memory[symbol][direction] = signal_memory[symbol][direction][-MAX_SIGNALS_PER_SYMBOL:]
        
        if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
            del signal_memory[symbol]
    
    if cleanup_count > 0:
        print(f"🧹 تم تنظيف {cleanup_count} إشارة قديمة")

# تحليل سياق الرسالة
def analyze_message_context(message):
    """تحليل تلقائي لسياق الرسالة"""
    message_lower = message.lower()
    
    context_hints = {
        "TECH": ["tech", "software", "iphone", "mac", "computer", "apple"],
        "FINANCIAL": ["bank", "credit", "payment", "financial", "visa", "mastercard"],
        "ENERGY": ["oil", "gas", "energy", "petroleum", "crude", "brent"],
        "CRYPTO": ["crypto", "bitcoin", "ethereum", "blockchain", "btc", "eth"],
        "INDEX": ["index", "spx", "nasdaq", "dow", "s&p", "500"],
        "METALS": ["gold", "silver", "xau", "xag", "metal", "precious"],
        "RETAIL": ["retail", "store", "shop", "consumer", "amazon", "walmart"]
    }
    
    for context, keywords in context_hints.items():
        if any(keyword in message_lower for keyword in keywords):
            return context
    
    return "GENERAL"

# معالجة الرموز القصيرة
def handle_short_symbols(message, extracted_symbol):
    """معالجة خاصة للرموز القصيرة التي يمكن أن تكون جزءاً من كلمات أخرى"""
    message_upper = message.upper()
    
    short_symbols = {
        "V": ["VISA", "CREDIT", "PAYMENT", "FINANCIAL", "BANK"],
        "M": ["MACY", "MARKET", "MORNING", "MACYS"],
        "C": ["CITI", "CITIGROUP", "CREDIT", "BANK"],
        "T": ["AT&T", "TELE", "TECH", "TELEPHONE", "TMOBILE"],
        "X": ["XEROX", "XBOX", "XILINX"]
    }
    
    # إذا كان الرمز قصيراً وليس في قائمة الرموز القصيرة المعروفة
    if len(extracted_symbol) <= 2 and extracted_symbol not in short_symbols:
        print(f"   ⚠️  رمز قصير غير معروف: {extracted_symbol} - سيتم تجاهله")
        return "UNKNOWN"
    
    if extracted_symbol in short_symbols:
        contexts = short_symbols[extracted_symbol]
        # إذا كان الرمز قصيراً، نتأكد من وجود السياق
        has_context = any(context in message_upper for context in contexts)
        
        if not has_context:
            # إذا لا يوجد سياق، نعتبره غير معروف
            print(f"   ⚠️  لا يوجد سياق للرمز القصير: {extracted_symbol} - سيتم تجاهله")
            return "UNKNOWN"
    
    return extracted_symbol

# استخراج الرمز بشكل محسن مع السياق
def extract_symbol(message):
    message_upper = message.upper()
    
    # البحث الدقيق بالرموز مع حدود الكلمات
    for symbol in STOCK_LIST:
        # استخدام regex للتأكد من أن الرمز ليس جزءاً من كلمة أخرى
        if re.search(r'\b' + re.escape(symbol) + r'\b', message_upper):
            print(f"   ✅ تم العثور على الرمز: {symbol} في الرسالة")
            return symbol
    
    # إذا لم يتم العثور على أي رمز
    print(f"   ⚠️  لم يتم العثور على أي رمز في الرسالة: {message_upper}")
    return "UNKNOWN"

# تنظيف اسم الإشارة للعرض فقط
def extract_clean_signal_name(raw_signal):
    if not raw_signal or len(raw_signal.strip()) < 2:
        return raw_signal
    
    clean_signal = raw_signal.upper()
    
    # إزالة الرموز فقط للعرض
    for symbol in STOCK_LIST:
        clean_signal = clean_signal.replace(symbol, '')
    
    clean_signal = re.sub(r'_\d+\.\d+', '', clean_signal)
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    clean_signal = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', clean_signal)
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    
    return clean_signal if clean_signal else raw_signal

# الحصول على الإشارات الحالية للرمز والاتجاه
def get_current_signals_info(symbol, direction):
    """الحصول على معلومات منسقة عن الإشارات الحالية"""
    signals = signal_memory.get(symbol, {}).get(direction, [])
    if not signals:
        return "لا توجد إشارات حتى الآن"
    
    unique_signal_ids = set()
    signal_details = []
    
    for sig, ts, signal_id in signals:
        if signal_id not in unique_signal_ids:
            unique_signal_ids.add(signal_id)
            clean_signal = extract_clean_signal_name(sig)
            signal_details.append((clean_signal, ts))
    
    signal_count = len(signals)
    unique_count = len(unique_signal_ids)
    
    # التحقق من وقت التصفير
    current_time = datetime.utcnow()
    time_remaining = RESET_TIMEOUT - (current_time - last_signal_time).total_seconds()
    minutes_remaining = max(0, int(time_remaining // 60))
    seconds_remaining = max(0, int(time_remaining % 60))
    
    info = f"الحالية: {signal_count} إشارة، الفريدة: {unique_count} نوع"
    info += f"\n⏰ وقت التصفير المتبقي: {minutes_remaining}:{seconds_remaining:02d}"
    
    if unique_signal_ids:
        info += f"\n📋 الإشارات الحالية:\n"
        for i, (signal_name, ts) in enumerate(signal_details[:10], 1):
            time_str = ts.strftime('%H:%M:%S') if ts else "غير معروف"
            info += f"   {i}. {signal_name} (منذ {time_str})\n"
    
    return info

# فحص تفرد الإشارة باستخدام الأرقام التسلسلية
def has_required_different_signals(signals_list):
    global last_signal_time, duplicate_signals
    
    # التحقق إذا حان وقت تصفير العد
    current_time = datetime.utcnow()
    time_since_last = (current_time - last_signal_time).total_seconds()
    
    if time_since_last > RESET_TIMEOUT:
        print("🔄 تصفير العد بسبب انتهاء المهلة (15 دقيقة)")
        duplicate_signals.clear()
        last_signal_time = current_time
        # مسح جميع الإشارات القديمة
        for symbol in signal_memory:
            for direction in ["bullish", "bearish"]:
                signal_memory[symbol][direction] = []
        return False, []
    
    if len(signals_list) < REQUIRED_SIGNALS:
        return False, []
    
    unique_signal_ids = set()
    unique_signals_info = []
    
    for sig, ts, signal_id in signals_list:
        # تخطي الإشارات المكررة المسجلة مسبقاً
        if signal_id in duplicate_signals:
            print(f"⏭️  تخطي إشارة مكررة (ID: {signal_id})")
            continue
            
        # التحقق من التكرار باستخدام الرقم التسلسلي
        if signal_id not in unique_signal_ids:
            unique_signal_ids.add(signal_id)
            unique_signals_info.append((signal_mapping[signal_id], ts))
        
        if len(unique_signal_ids) >= REQUIRED_SIGNALS:
            # إرجاع النصوص الأصلية للإشارات الفريدة
            unique_signals = [signal_mapping[sid] for sid in list(unique_signal_ids)[:REQUIRED_SIGNALS]]
            return True, unique_signals
    
    return False, [signal_mapping[sid] for sid in unique_signal_ids]

# معالجة التنبيهات المحسنة مع تسجيل محسن
def process_alerts(alerts):
    global last_signal_time, duplicate_signals
    
    start_time = time.time()
    
    for alert in alerts:
        if isinstance(alert, dict):
            signal = alert.get("signal", alert.get("message", "")).strip()
            ticker = alert.get("ticker", "").strip().upper()
        else:
            signal = str(alert).strip()
            ticker = ""

        if not signal:
            continue

        message_upper = signal.upper()
        print(f"🔍 تحليل الرسالة: '{signal}'")
        
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)
            print(f"   الرمز المستخرج: {ticker}")
            
        # منع التعيين التلقائي لرموز غير موجودة في الرسالة
        if ticker != "UNKNOWN" and ticker not in message_upper:
            print(f"   ⚠️  الرمز {ticker} غير موجود في الرسالة - سيتم تجاهله")
            ticker = "UNKNOWN"
            
        # معالجة الرموز القصيرة
        if len(ticker) <= 2 and ticker != "UNKNOWN":
            old_ticker = ticker
            ticker = handle_short_symbols(signal, ticker)
            if ticker != old_ticker:
                print(f"   تم تغيير الرمز من {old_ticker} إلى {ticker}")

        if ticker == "UNKNOWN":
            context = analyze_message_context(signal)
            print(f"⚠️  لم يتم التعرف على الرمز: {signal}")
            print(f"   السياق: {context}")
            continue

        signal_lower = signal.lower()
        direction = "bearish" if any(word in signal_lower for word in ["bearish", "down", "put", "short", "sell"]) else "bullish"

        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": []}
        
        current_signals = signal_memory[ticker][direction]
        
        # التحقق من التكرار قبل التخزين
        signal_id = generate_signal_id(signal)
        
        # إذا كانت الإشارة مكررة (نفس المحتوى موجود مسبقاً)
        is_duplicate = False
        for existing_sig, existing_ts, existing_id in current_signals:
            if existing_sig == signal:
                print(f"🚫 إشارة مكررة - تم تجاهلها: {signal}")
                duplicate_signals.add(signal_id)
                is_duplicate = True
                break
        
        if is_duplicate:
            continue
            
        if len(current_signals) >= MAX_SIGNALS_PER_SYMBOL:
            current_signals.pop(0)
        
        # تخزين الإشارة مع الرقم التسلسلي
        current_signals.append((signal, datetime.utcnow(), signal_id))
        last_signal_time = datetime.utcnow()
        
        # تسجيل مفصل
        clean_signal_name = extract_clean_signal_name(signal)
        context = analyze_message_context(signal)
        print(f"✅ تم تخزين إشارة {direction} لـ {ticker} (ID: {signal_id}): {clean_signal_name}")
        print(f"   السياق: {context}")

    # التنظيف الدوري
    if random.random() < 0.3:
        cleanup_signals()

    # التحقق من الإشارات المطلوبة مع تسجيل محسن
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count > 0:
                signals_info = get_current_signals_info(symbol, direction)
                has_required, unique_signals = has_required_different_signals(signals[direction])
                
                if has_required:
                    saudi_time = get_saudi_time()
                    
                    # تنظيف وتنسيق الإشارات للعرض
                    formatted_signals = []
                    for signal_text in unique_signals[:REQUIRED_SIGNALS]:
                        clean_signal = extract_clean_signal_name(signal_text)
                        # تقصير الإشارات الطويلة
                        if len(clean_signal) > 50:
                            clean_signal = clean_signal[:47] + "..."
                        formatted_signals.append(f'• {clean_signal}')
                    
                    if direction == "bullish":
                        message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية قوية</b>

📊 <b>الإشارات المختلفة:</b>
{chr(10).join(formatted_signals)}

🔢 <b>عدد الإشارات الكلي:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد صعودي قوي من {REQUIRED_SIGNALS} إشارات مختلفة - متوقع حركة صعودية</code>"""
                    else:
                        message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية قوية</b>

📊 <b>الإشارات المختلفة:</b>
{chr(10).join(formatted_signals)}

🔢 <b>عدد الإشارات الكلي:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>تأكيد هبوطي قوي من {REQUIRED_SIGNALS} إشارات مختلفة - متوقع حركة هبوطية</code>"""
                    
                    telegram_success = send_telegram_to_all(message)
                    external_success = send_post_request(message, f"{direction.upper()} signals", 
                                                       "BULLISH_CONFIRMATION" if direction == "bullish" else "BEARISH_CONFIRMATION")
                    
                    if telegram_success:
                        print(f"🎉 تم إرسال التنبيه بنجاح لـ {symbol} ({direction})")
                    
                    # تصفير الذاكرة بعد الإرسال الناجح
                    signal_memory[symbol][direction] = []
                    duplicate_signals.clear()
                    last_signal_time = datetime.utcnow()
                    
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
        # التحقق من الطلبات المكررة
        request_hash = hash(request.get_data())
        current_time = time.time()
        
        if request_hash in request_cache:
            if current_time - request_cache[request_hash] < CACHE_DURATION:
                print("🔄 تخطي الطلب المكرر")
                return jsonify({"status": "duplicate_skipped"}), 200
        
        request_cache[request_hash] = current_time
        # تنظيف ذاكرة التخزين المؤقت القديمة
        for key in list(request_cache.keys()):
            if current_time - request_cache[key] > CACHE_DURATION * 2:
                del request_cache[key]
                
        alerts = []
        raw_data = None

        # تسجيل البيانات الخام
        try:
            raw_data = request.get_data(as_text=True).strip()
            print(f"📨 تم استقبال بيانات webhook الخام: '{raw_data}'")
            print(f"📦 طول البيانات: {len(raw_data)} حرف")
            print(f"🔍 أول 100 حرف: {raw_data[:100]}{'...' if len(raw_data) > 100 else ''}")
            
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
    current_time = datetime.utcnow()
    time_remaining = RESET_TIMEOUT - (current_time - last_signal_time).total_seconds()
    minutes_remaining = max(0, int(time_remaining // 60))
    seconds_remaining = max(0, int(time_remaining % 60))
    
    return jsonify({
        "status": "running",
        "message": "مستقبل webhook الخاص بـ TradingView نشط",
        "monitored_stocks": STOCK_LIST,
        "required_signals": REQUIRED_SIGNALS,
        "active_signals": {k: f"{len(v['bullish']) + len(v['bearish'])} signals" for k, v in signal_memory.items()},
        "signal_counter": signal_counter,
        "duplicate_signals_count": len(duplicate_signals),
        "reset_time_remaining": f"{minutes_remaining}:{seconds_remaining:02d}",
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
    print(f"🟢 وقت تصفير العد: 15 دقيقة")
    print(f"🟢 API الخارجي: https://backend-thrumming-moon-2807.fly.dev/sendMessage")
    print("🟢 في انتظار webhooks من TradingView...")
    app.run(host="0.0.0.0", port=port)
