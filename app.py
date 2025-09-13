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
TEST_MODE = True  # True للاختبار بدون إشارات ترند، False للوضع الطبيعي

# كاش للإشارات المعالجة
signal_cache = {}
CACHE_TIMEOUT = 300

# تتبع إشارات Trend Catcher و Trend Tracer بشكل منفصل
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

# ذاكرة الإشارات العادية فقط
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

# تنظيف الإشارات العادية القديمة فقط
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

# الكشف عن إشارات الترند وتحديثها
def check_and_update_trend_signals(signal_text, symbol):
    signal_lower = signal_text.lower()
    is_trend_signal = False
    
    # كلمات مفتاحية للكشف عن إشارات الترند
    trend_keywords = ['trend', 'catcher', 'tracer', 'direction', 'اتجاه', 'ترند']
    bullish_keywords = ['bullish', 'up', 'call', 'long', 'buy', 'صاعد', 'شراء']
    bearish_keywords = ['bearish', 'down', 'put', 'short', 'sell', 'هابط', 'بيع']
    
    # التحقق إذا كانت الإشارة تحتوي على كلمات ترند
    has_trend_keyword = any(keyword in signal_lower for keyword in trend_keywords)
    
    if has_trend_keyword:
        # تحديد الاتجاه
        if any(word in signal_lower for word in bullish_keywords):
            direction = "bullish"
        elif any(word in signal_lower for word in bearish_keywords):
            direction = "bearish"
        else:
            print(f"📊 إشارة ترند بدون اتجاه واضح لـ {symbol}")
            return True
        
        # الكشف عن Trend Catcher
        if 'catcher' in signal_lower:
            current_direction = trend_signals[symbol]["trend_catcher"]
            
            if current_direction is None or current_direction[0] != direction:
                trend_signals[symbol]["trend_catcher"] = (direction, datetime.utcnow())
                print(f"📊 Trend Catcher تم تحديثه إلى {direction} لـ {symbol}")
            
            is_trend_signal = True
        
        # الكشف عن Trend Tracer
        elif 'tracer' in signal_lower:
            current_direction = trend_signals[symbol]["trend_tracer"]
            
            if current_direction is None or current_direction[0] != direction:
                trend_signals[symbol]["trend_tracer"] = (direction, datetime.utcnow())
                print(f"📊 Trend Tracer تم تحديثه إلى {direction} لـ {symbol}")
            
            is_trend_signal = True
        
        # إذا كانت إشارة ترند عامة
        else:
            print(f"📊 إشارة ترند عامة لـ {symbol}: {direction}")
            is_trend_signal = True
    
    return is_trend_signal

# الحصول على معلومات الإشارات العادية الحالية
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

# التحقق من وجود إشارات عادية مختلفة مطلوبة
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

# التحقق من محاذاة إشارات الترند
def check_trend_alignment(symbol, direction):
    trend_catcher = trend_signals[symbol]["trend_catcher"]
    trend_tracer = trend_signals[symbol]["trend_tracer"]
    
    if trend_catcher is None and trend_tracer is None:
        print(f"⚠️ لا توجد إشارات ترند لـ {symbol}")
        return False
    
    if trend_catcher and trend_catcher[0] == direction:
        print(f"✅ Trend Catcher متوافق مع {direction} لـ {symbol}")
        return True
    
    if trend_tracer and trend_tracer[0] == direction:
        print(f"✅ Trend Tracer متوافق مع {direction} لـ {symbol}")
        return True
    
    print(f"❌ إشارات الترند غير متوافقة مع {direction} لـ {symbol}")
    return False

# الحصول على حالة إشارات الترند
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

        # التحقق من إشارات الترند أولاً
        is_trend_signal = check_and_update_trend_signals(signal, ticker)
        
        # معالجة الإشارات العادية فقط
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
            print(f"📊 تم معالجة إشارة ترند لـ {ticker}")

    # تنظيف الإشارات العادية
    if random.random() < 0.3:
        cleanup_signals()

    # التحقق من إمكانية إرسال تنبيهات
    for symbol, signals in list(signal_memory.items()):
        for direction in ["bullish", "bearish"]:
            signal_count = len(signals[direction])
            if signal_count > 0:
                signals_info = get_current_signals_info(symbol, direction)
                has_required, unique_signals = has_required_different_signals(signals[direction])
                
                trend_aligned = check_trend_alignment(symbol, direction)
                
                # السماح بالإرسال في وضع الاختبار حتى بدون إشارات ترند
                if has_required and (trend_aligned or TEST_MODE):
                    saudi_time = get_saudi_time()
                    trend_status = get_trend_status(symbol)
                    
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
                    external_success = send_post_request(message, f"{direction.upper()} signals", 
                                                       "BUY_CONFIRMATION" if direction == "bullish" else "SELL_CONFIRMATION")
                    
                    if telegram_success:
                        print(f"🎉 تم إرسال تنبيه دخول صفقة لـ {symbol} ({direction})")
                        signal_memory[symbol][direction] = []
                    
                else:
                    print(f"⏳ في انتظار شروط التنبيه لـ {symbol} ({direction})")
                    print(f"   {signals_info}")
                    print(f"   تحتاج {REQUIRED_SIGNALS} إشارات عادية مختلفة، حالياً لديك {len(unique_signals)}")
                    print(f"   {get_trend_status(symbol)}")
                    
                    if time.time() - start_time > 2.0:
                        return

# ... (بقية الكود بدون تغيير)
