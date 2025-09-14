# tradingview_webhook_improved.py
# نسخة محسّنة من مستقبل webhook مخصّص لـ TradingView
# - معالجة التصفير بعد الإرسال مباشرة
# - تصفير بعد 15 دقيقة بدون إشارات مختلفة
# - منع التكرار النصي بدقة باستخدام تجزئة المحتوى
# - حماية المتغيرات المشتركة (thread-safe)
# - تحسينات على طلبات الشبكة (hash ثابت للـ request cache، retries)

from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict, deque
import json
import re
import time
import random
import threading
import hashlib
import logging

# ---------------------- إعداد السجل (logging) ----------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
log = logging.getLogger("tv-webhook")

# ---------------------- الإعدادات القابلة للتعديل ----------------------
TIMEZONE_OFFSET = 3  # توقيت السعودية UTC+3
REQUIRED_SIGNALS = 2
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c")
CHAT_ID = os.environ.get("CHAT_ID", "624881400")
RESET_TIMEOUT = 15 * 60  # 15 دقيقة بالثواني
CACHE_DURATION = 30  # ثواني
MAX_SIGNALS_PER_SYMBOL = 50  # حفظ آخر N إشارات لكل رمز/اتجاه
NETWORK_TIMEOUT = 8  # ثواني لطلبات الشبكة
NETWORK_RETRIES = 2

# ---------------------- هياكل بيانات الحالة العالمية (محمية) ----------------------
state_lock = threading.RLock()
signal_counter = 0  # عداد تسلسلي للعرض البشري
# mapping: content_hash -> {serial:int, text:str, first_seen:datetime}
signal_mapping = {}
# duplicate_signals: content_hash -> timestamp_when_seen
duplicate_signals = {}
# signal_memory: symbol -> {"bullish": deque([...]), "bearish": deque([...])}
# كل عنصر في القائمة: {"text":..., "ts":datetime, "hash":..., "serial":...}
signal_memory = defaultdict(lambda: {"bullish": deque(), "bearish": deque()})
# طلبات مخبأة لتفادي التكرار المباشر: req_hash -> timestamp
request_cache = {}

# آخر وقت تلقى فيه إشارة فريدة (None يعني لا توجد إشارة حتى الآن)
last_unique_signal_time = None

app = Flask(__name__)
session = requests.Session()

# ---------------------- أدوات مساعدة ----------------------

def compute_hash(text: str) -> str:
    """تجزئة ثابتة لمحتوى الإشارة لاكتشاف التكرار النصي بدقة"""
    if text is None:
        text = ""
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def get_saudi_time() -> str:
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')


def remove_html_tags(text: str) -> str:
    if not text:
        return text
    return re.sub(r'<.*?>', '', text)


# ---------------------- تحميل قائمة الأسهم ----------------------
_stock_list_cache = None
_stock_list_cache_time = 0

def load_stocks(filename='stocks.txt'):
    global _stock_list_cache, _stock_list_cache_time
    try:
        if _stock_list_cache and time.time() - _stock_list_cache_time < 300:
            return _stock_list_cache
        stocks = []
        with open(filename, 'r', encoding='utf-8') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
        _stock_list_cache = stocks
        _stock_list_cache_time = time.time()
        return stocks
    except Exception as e:
        log.warning(f"لم أجد {filename} أو حدث خطأ في قراءته: {e} - سيتم استخدام قائمة افتراضية")
        _stock_list_cache = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30", "XAUUSD", "XAGUSD", "USOIL"]
        _stock_list_cache_time = time.time()
        return _stock_list_cache

STOCK_LIST = load_stocks()
# ترتيب الرموز بحسب الطول تنازليًا لتفادي المطابقة الجزئية (مثلاً MATCH LONG before SHORT)
STOCK_LIST_SORTED = sorted(STOCK_LIST, key=lambda x: -len(x))

# ---------------------- طلبات الشبكة مع retry بسيط ----------------------

def post_with_retries(url, json_payload=None, timeout=NETWORK_TIMEOUT, retries=NETWORK_RETRIES):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = session.post(url, json=json_payload, timeout=timeout)
            return resp
        except Exception as e:
            last_exc = e
            log.warning(f"خطأ في الطلب إلى {url} (attempt {attempt+1}): {e}")
            time.sleep(0.5 * (attempt + 1))
    # آخر محاولة فاشلة
    log.error(f"جميع محاولات الاتصال بـ {url} فشلت: {last_exc}")
    return None


# ---------------------- إرسال تلغرام وتحقق أوضح من النجاح ----------------------

def send_telegram_to_all(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    resp = post_with_retries(url, json_payload=payload)
    if not resp:
        return False
    try:
        j = resp.json()
        ok = j.get("ok", False)
        if not ok:
            log.warning(f"Telegram API returned ok=False: {j}")
        return ok
    except Exception:
        # إذا لم نستطع تحليل JSON، نعتبر الفشل إذا لم يكن 200
        return resp.status_code == 200


# ---------------------- طلب POST خارجي ----------------------

def send_post_request(message: str, indicators: str, signal_type: str = None) -> bool:
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
    resp = post_with_retries(url, json_payload=payload)
    if not resp:
        return False
    return resp.status_code == 200


# ---------------------- استخراج الرمز ----------------------

def extract_symbol(message: str) -> str:
    message_upper = (message or "").upper()
    # نبحث عن الرموز الأطول أولاً لتفادي التطابق الجزئي
    for symbol in STOCK_LIST_SORTED:
        # نستخدم حدود كلمات مرنة: لا نريد أن يكون جزءاً من كلمة أبجدية رقمية أخرى
        pattern = rf'(?<![A-Z0-9_\-\.]){re.escape(symbol)}(?![A-Z0-9_\-\.])'
        if re.search(pattern, message_upper):
            log.debug(f"تم العثور على الرمز {symbol} في الرسالة")
            return symbol
    log.debug("لم يتم التعرف على أي رمز")
    return "UNKNOWN"


# ---------------------- تنظيف اسم الإشارة ----------------------

def extract_clean_signal_name(raw_signal: str) -> str:
    if not raw_signal or len(raw_signal.strip()) < 2:
        return raw_signal
    clean_signal = raw_signal.upper()
    for symbol in STOCK_LIST:
        clean_signal = clean_signal.replace(symbol, '')
    clean_signal = re.sub(r'_\d+\.\d+', '', clean_signal)
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    clean_signal = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', clean_signal)
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    return clean_signal if clean_signal else raw_signal


# ---------------------- تحليل سياق الرسالة ----------------------

def analyze_message_context(message: str) -> str:
    message_lower = (message or "").lower()
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


# ---------------------- معالجة الرموز القصيرة ----------------------

def handle_short_symbols(message: str, extracted_symbol: str) -> str:
    message_upper = (message or "").upper()
    short_symbols = {
        "V": ["VISA", "CREDIT", "PAYMENT", "FINANCIAL", "BANK"],
        "M": ["MACY", "MARKET", "MORNING", "MACYS"],
        "C": ["CITI", "CITIGROUP", "CREDIT", "BANK"],
        "T": ["AT&T", "TELE", "TECH", "TELEPHONE", "TMOBILE"],
        "X": ["XEROX", "XBOX", "XILINX"]
    }
    if not extracted_symbol or len(extracted_symbol) <= 2:
        if extracted_symbol not in short_symbols:
            log.debug(f"رمز قصير غير معروف: {extracted_symbol}")
            return "UNKNOWN"
    if extracted_symbol in short_symbols:
        contexts = short_symbols[extracted_symbol]
        has_context = any(context in message_upper for context in contexts)
        if not has_context:
            log.debug(f"لا يوجد سياق للرمز القصير: {extracted_symbol}")
            return "UNKNOWN"
    return extracted_symbol


# ---------------------- تنظيف الإشارات والذاكرة ----------------------

def cleanup_signals():
    global duplicate_signals
    with state_lock:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=RESET_TIMEOUT)
        removed = 0

        # تنظيف duplicate_signals حسب الوقت
        old_hashes = [h for h, ts in duplicate_signals.items() if (now - ts).total_seconds() > RESET_TIMEOUT]
        for h in old_hashes:
            del duplicate_signals[h]
            removed += 1

        # تنظيف إشارات قديمة من signal_memory
        for symbol in list(signal_memory.keys()):
            for direction in ["bullish", "bearish"]:
                dq = signal_memory[symbol][direction]
                orig_len = len(dq)
                # احتفظ فقط بالإشارات الحديثة حتى MAX_SIGNALS_PER_SYMBOL
                while len(dq) > MAX_SIGNALS_PER_SYMBOL:
                    dq.popleft()
                # إزالة العناصر الأقدم من cutoff
                filtered = deque([item for item in dq if (now - item['ts']).total_seconds() <= RESET_TIMEOUT])
                if len(filtered) != orig_len:
                    removed += (orig_len - len(filtered))
                    signal_memory[symbol][direction] = filtered

            # حذف المفتاح إذا لا يوجد إشارات
            if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
                del signal_memory[symbol]

        if removed:
            log.info(f"🧹 تنظيف: تم إزالة {removed} مدخلة قديمة")


# ---------------------- التحقق من وجود إشارات مختلفة كافية ----------------------

def has_required_different_signals(signals_list):
    """تأخذ قائمة العناصر (كل عنصر dict) وتحدد إذا كان هناك REQUIRED_SIGNALS فريدة"""
    unique_hashes = []
    seen = set()
    for item in signals_list:
        h = item['hash']
        if h not in seen:
            seen.add(h)
            unique_hashes.append(h)
            if len(unique_hashes) >= REQUIRED_SIGNALS:
                break
    if len(unique_hashes) >= REQUIRED_SIGNALS:
        # إرجاع True مع النصوص (من mapping) للإشارات الفريدة
        texts = [signal_mapping.get(h, {}).get('text', '<unknown>') for h in unique_hashes[:REQUIRED_SIGNALS]]
        return True, texts, unique_hashes[:REQUIRED_SIGNALS]
    return False, [], unique_hashes


# ---------------------- معالجة التنبيهات ----------------------

def process_alerts(alerts):
    """يعالج لائحة من التنبيهات (قابلة لأن تكون dict أو نص)"""
    global last_unique_signal_time
    now = datetime.utcnow()
    with state_lock:
        new_unique_seen = False

    start_time = time.time()

    for alert in alerts:
        # استخراج نص الإشارة والرمز
        if isinstance(alert, dict):
            signal_text = (alert.get('signal') or alert.get('message') or alert.get('text') or '').strip()
            ticker = (alert.get('ticker') or alert.get('symbol') or '').strip().upper()
        else:
            signal_text = str(alert).strip()
            ticker = ''

        if not signal_text:
            continue

        message_upper = signal_text.upper()
        log.info(f"🔍 معالجة: {signal_text}")

        if not ticker or ticker == 'UNKNOWN':
            ticker = extract_symbol(signal_text)

        if ticker != 'UNKNOWN' and ticker not in message_upper:
            # إذا تم استخراج ticker لكنه غير موجود نصيًا، اعتبر UNKNOWN
            ticker = 'UNKNOWN'

        if len(ticker) <= 2 and ticker != 'UNKNOWN':
            ticker_checked = handle_short_symbols(signal_text, ticker)
            if ticker_checked == 'UNKNOWN':
                ticker = 'UNKNOWN'

        if ticker == 'UNKNOWN':
            context = analyze_message_context(signal_text)
            log.info(f"⚠️ لم يتم التعرف على رمز للإشارة. السياق: {context} - سيتم تجاهل الإشارة")
            continue

        # تحديد اتجاه الإشارة
        s_lower = signal_text.lower()
        direction = 'bearish' if any(w in s_lower for w in ['bearish', 'down', 'put', 'short', 'sell']) else 'bullish'

        # حساب تجزئة المحتوى
        content_hash = compute_hash(signal_text)

        with state_lock:
            # تحقق من التكرار: إذا ظهر hash سابقًا خلال نافذة التصفير الحاليّة، اعتبر تكراراً
            if content_hash in duplicate_signals:
                log.info(f"⏭️ إشارة مكررة (hash): {content_hash} - سيتم تجاهلها")
                continue

            # توليد رقم تسلسلي عرضي
            global signal_counter
            signal_counter += 1
            serial = signal_counter
            signal_mapping[content_hash] = {'serial': serial, 'text': signal_text, 'first_seen': now}
            # إضافة إلى ذاكرة الإشارات للرمز والاتجاه
            item = {'text': signal_text, 'ts': now, 'hash': content_hash, 'serial': serial}
            dq = signal_memory[ticker][direction]
            dq.append(item)
            # إضافة إلى duplicate_signals مع طابع زمني
            duplicate_signals[content_hash] = now
            # تحديث آخر وقت لإشارة فريدة
            last_unique_signal_time = now
            new_unique_seen = True
            log.info(f"✅ خزّننا إشارة {direction} لـ {ticker} (serial={serial})")

        # تجنب إطالة الحلقة لو كانت دفعة ضخمة - لكن لا نقطع معالجة التنبيهات
        if time.time() - start_time > 5.0:
            log.info("⚠️ معالجة طويلة — الأن سأكمل ولكن قد تستغرق الدفعة وقتا")

    # تنظيف دوري
    if random.random() < 0.4:
        cleanup_signals()

    # بعد حفظ الإشارات، نتحقق هل وصلنا لعدد إشارات كافي لكل رمز/اتجاه
    with state_lock:
        for symbol, dirs in list(signal_memory.items()):
            for direction in ['bullish', 'bearish']:
                dq = dirs[direction]
                if not dq:
                    continue
                has_req, unique_texts, unique_hashes = has_required_different_signals(list(dq))
                if has_req:
                    saudi_time = get_saudi_time()
                    # تنسيق الإشارات للعرض
                    formatted = []
                    for t in unique_texts[:REQUIRED_SIGNALS]:
                        clean = extract_clean_signal_name(t)
                        if len(clean) > 80:
                            clean = clean[:77] + '...'
                        formatted.append(f'• {clean}')

                    if direction == 'bullish':
                        message = f"🚀 <b>{symbol} - تأكيد إشارة صعودية قوية</b>\n\n📊 <b>الإشارات المختلفة:</b>\n{chr(10).join(formatted)}\n\n🔢 <b>عدد الإشارات الكلي:</b> {len(dq)}\n⏰ <b>التوقيت السعودي:</b> {saudi_time}\n\n<code>تأكيد صعودي قوي من {REQUIRED_SIGNALS} إشارات مختلفة - متوقع حركة صعودية</code>"
                    else:
                        message = f"📉 <b>{symbol} - تأكيد إشارة هبوطية قوية</b>\n\n📊 <b>الإشارات المختلفة:</b>\n{chr(10).join(formatted)}\n\n🔢 <b>عدد الإشارات الكلي:</b> {len(dq)}\n⏰ <b>التوقيت السعودي:</b> {saudi_time}\n\n<code>تأكيد هبوطي قوي من {REQUIRED_SIGNALS} إشارات مختلفة - متوقع حركة هبوطية</code>"

                    # إرسال التنبيهات
                    telegram_success = send_telegram_to_all(message)
                    external_success = send_post_request(message, f"{direction.upper()} signals", 
                                                         "BULLISH_CONFIRMATION" if direction == 'bullish' else "BEARISH_CONFIRMATION")

                    if telegram_success:
                        log.info(f"🎉 تم إرسال تنبيه Telegram لـ {symbol} ({direction})")
                    else:
                        log.warning(f"❌ فشل إرسال Telegram لـ {symbol} ({direction})")

                    if external_success:
                        log.info(f"✅ تم إرسال إلى API الخارجي لـ {symbol} ({direction})")
                    else:
                        log.warning(f"❌ فشل إرسال إلى API الخارجي لـ {symbol} ({direction})")

                    # التصفير بعد الإرسال: نزيل إشارات هذا الرمز والاتجاه فوراً
                    # ونحذف مفاتيح duplicate المرتبطة بهذه الإشارات حتى نتمكن من التقاطها لاحقاً
                    hashes_to_remove = {item['hash'] for item in dq}
                    for h in hashes_to_remove:
                        duplicate_signals.pop(h, None)
                        # لا نحذف من signal_mapping كي نحافظ على سجل العرض (يمكن تقليصه لاحقاً)

                    signal_memory[symbol][direction] = deque()
                    last_unique_signal_time = datetime.utcnow()
                    log.info(f"🔄 تم التصفير فورًا لـ {symbol} ({direction}) بعد الإرسال")

    return


# ---------------------- تسجيل الطلبات الواردة ----------------------
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        log.info(f"🌐 طلب وارد: {request.method} {request.path} - Content-Type: {request.content_type}")


# ---------------------- Webhook endpoint ----------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw_bytes = request.get_data()
        # استخدام sha256 ثابت لمفتاح التخزين المؤقت
        req_hash = hashlib.sha256(raw_bytes).hexdigest()
        now_ts = time.time()

        with state_lock:
            # تنظيف عناصر التخزين المؤقت القديمة
            old_keys = [k for k, t in request_cache.items() if now_ts - t > CACHE_DURATION * 2]
            for k in old_keys:
                del request_cache[k]

            # التحقق من التكرار المباشر
            if req_hash in request_cache and now_ts - request_cache[req_hash] < CACHE_DURATION:
                log.info("🔄 تخطي طلب webhook مكرر (cache)")
                return jsonify({"status": "duplicate_skipped"}), 200

            request_cache[req_hash] = now_ts

        raw_text = raw_bytes.decode('utf-8', errors='ignore').strip()
        log.info(f"📨 بيانات webhook ({len(raw_text)} chars): {raw_text[:200]}")

        alerts = []
        # محاولة تحليل JSON
        try:
            if raw_text.startswith('{') or raw_text.startswith('['):
                data = json.loads(raw_text)
                if isinstance(data, dict):
                    if 'alerts' in data and isinstance(data['alerts'], list):
                        alerts = data['alerts']
                    else:
                        alerts = [data]
                elif isinstance(data, list):
                    alerts = data
            else:
                # إذا لم يكن JSON، خزن النص كإشارة مفردة
                alerts = [{"signal": raw_text, "raw_data": raw_text}]
        except json.JSONDecodeError:
            # فشل التحليل => اعتبر النص كتنبيه واحد
            alerts = [{"signal": raw_text, "raw_data": raw_text}]

        if not alerts and request.is_json:
            try:
                data = request.get_json(force=True)
                if isinstance(data, dict):
                    alerts = [data]
                elif isinstance(data, list):
                    alerts = data
            except Exception as e:
                log.warning(f"فشل parse JSON من request.get_json: {e}")

        if not alerts:
            log.warning("⚠️ لم يتم العثور على أي تنبيهات بعد المحاولات - تجاهل")
            return jsonify({"status": "no_alerts"}), 200

        # معالجة التنبيهات
        process_alerts(alerts)
        return jsonify({"status": "alert_processed", "count": len(alerts), "timestamp": datetime.utcnow().isoformat()}), 200

    except Exception as e:
        log.exception(f"❌ خطأ في webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


# ---------------------- الصفحة الرئيسية للفحص ----------------------
@app.route('/')
def home():
    with state_lock:
        if last_unique_signal_time:
            elapsed = (datetime.utcnow() - last_unique_signal_time).total_seconds()
            time_remaining = max(0, RESET_TIMEOUT - elapsed)
        else:
            time_remaining = 0

        minutes = int(time_remaining // 60)
        seconds = int(time_remaining % 60)

        active_signals = {k: f"{len(v['bullish']) + len(v['bearish'])} signals" for k, v in signal_memory.items()}
        return jsonify({
            "status": "running",
            "message": "مستقبل webhook الخاص بـ TradingView نشط (محسّن)",
            "monitored_stocks": STOCK_LIST,
            "required_signals": REQUIRED_SIGNALS,
            "active_signals": active_signals,
            "signal_counter": signal_counter,
            "duplicate_signals_count": len(duplicate_signals),
            "reset_time_remaining": f"{minutes}:{seconds:02d}",
            "timestamp": datetime.utcnow().isoformat()
        })


# ---------------------- اختبار الخدمات ----------------------

def test_services():
    log.info("جاري اختبار الخدمات...")
    try:
        telegram_result = send_telegram_to_all("🔧 رسالة اختبار من البوت - النظام يعمل!")
        external_result = send_post_request("رسالة اختبار", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
        log.info(f"نتيجة اختبار التلغرام: {telegram_result}, نتيجة API الخارجي: {external_result}")
        return telegram_result and external_result
    except Exception as e:
        log.exception(f"فشل اختبار الخدمات: {e}")
        return False


# ---------------------- نقطة الدخول ----------------------
if __name__ == '__main__':
    # اختبار الخدمات (غير حاسم للتشغيل)
    test_services()

    port = int(os.environ.get('PORT', 10000))
    log.info(f"🟢 بدء الخادم على 0.0.0.0:{port} - مراقبة: {', '.join(STOCK_LIST)} - UTC+{TIMEZONE_OFFSET}")
    app.run(host='0.0.0.0', port=port)
