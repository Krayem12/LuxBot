from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import os
from collections import defaultdict
import json
import re

app = Flask(__name__)

# 🔹 إعداد التوقيت السعودي (UTC+3)
TIMEZONE_OFFSET = 3
REQUIRED_SIGNALS = 3
TELEGRAM_TOKEN = "8058697981:AAFuImKvuSKfavBaE2TfqlEESPZb9Ql-X9c"
CHAT_ID = "624881400"

# 🔹 الحصول على التوقيت السعودي
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        print(f"✅ تم الإرسال إلى التليجرام: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطأ في إرسال التليجرام: {e}")
        return False

def load_stocks():
    try:
        with open('stocks.txt', 'r') as f:
            return [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        return ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30", "XAUUSD", "XAGUSD", "OIL"]

STOCK_LIST = load_stocks()
signal_memory = defaultdict(lambda: {"bullish": [], "bearish": []})

def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                sig_data for sig_data in signal_memory[symbol][direction] 
                if sig_data['timestamp'] > cutoff
            ]
        if not signal_memory[symbol]['bullish'] and not signal_memory[symbol]['bearish']:
            del signal_memory[symbol]

def extract_symbol(message, original_ticker=""):
    message_upper = message.upper()
    
    if original_ticker and original_ticker != "UNKNOWN":
        clean_ticker = re.sub(r'[^A-Z0-9]', '', original_ticker.upper())
        if clean_ticker in STOCK_LIST:
            return clean_ticker
    
    for symbol in sorted(STOCK_LIST, key=len, reverse=True):
        if re.search(r'\b' + re.escape(symbol) + r'\b', message_upper):
            return symbol
    
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

# ✅ التحقق من إشارات LuxAlgo بشكل دقيق
def is_luxalgo_signal(signal_text):
    """التأكد إذا كانت الإشارة من LuxAlgo"""
    luxalgo_patterns = [
        r'luxalgo', r'lux algo', r'hyperth', r'hyper_th', r'hypert',
        r'هايبيرث', r'هيبرث', r'هيبيرث', r'vip', r'premium',
        r'في أي بي', r'فاي بي', r'بريميوم', r'لوكس ألجو'
    ]
    
    signal_lower = signal_text.lower()
    return any(re.search(pattern, signal_lower) for pattern in luxalgo_patterns)

# ✅ تحديد اتجاه الإشارة بدقة عالية (مخصص لـ LuxAlgo)
def determine_signal_direction(signal_text, original_direction=""):
    """
    تحديد اتجاه الإشارة بدقة عالية مع التركيز على إشارات LuxAlgo
    """
    signal_lower = signal_text.lower()
    
    # أولاً: إذا كان هناك اتجاه محدد في البيانات الأصلية
    if original_direction:
        original_lower = original_direction.lower()
        if any(term in original_lower for term in ["bearish", "short", "sell", "هبوطي", "بيع", "هابط", "put", "down"]):
            return "bearish"
        elif any(term in original_lower for term in ["bullish", "long", "buy", "صعودي", "شراء", "صاعد", "call", "up"]):
            return "bullish"
    
    # ثانياً: البحث عن مصطلحات محددة في نص الإشارة
    bearish_indicators = [
        # مصطلحات إنجليزية
        "bearish", "bear", "short", "sell", "put", "down", "downside", "drop", 
        "decline", "fall", "dump", "crash", "breakdown",
        # مصطلحات عربية
        "هبوطي", "بيع", "هابط", "نزول", "هبوط", "تراجع", "انخفاض", "سقوط",
        # رموز وإيموجيات
        "📉", "🔻", "🔽", "⏬", "🔴"
    ]
    
    bullish_indicators = [
        # مصطلحات إنجليزية
        "bullish", "bull", "long", "buy", "call", "up", "upside", "rise",
        "rally", "jump", "pump", "breakout", "recovery",
        # مصطلحات عربية  
        "صعودي", "شراء", "صاعد", "صعود", "ارتفاع", "تحسن", "قفزة",
        # رموز وإيموجيات
        "📈", "🔺", "🔼", "⏫", "🟢"
    ]
    
    # عدّ المؤشرات لكل اتجاه
    bearish_count = sum(1 for term in bearish_indicators if term in signal_lower)
    bullish_count = sum(1 for term in bullish_indicators if term in signal_lower)
    
    print(f"📊 Bearish indicators: {bearish_count}, Bullish indicators: {bullish_count}")
    
    # تحديد الاتجاه بناءً على الأغلبية
    if bearish_count > bullish_count:
        return "bearish"
    elif bullish_count > bearish_count:
        return "bullish"
    
    # ثالثاً: إذا كانت متساوية، نبحث عن أنماط LuxAlgo المحددة
    luxalgo_bearish_patterns = [
        r'hyperth.*bearish', r'hyperth.*short', r'hyperth.*sell',
        r'هايبيرث.*هبوطي', r'هايبيرث.*بيع', r'vip.*bearish', r'vip.*short',
        r'premium.*bearish', r'premium.*short'
    ]
    
    luxalgo_bullish_patterns = [
        r'hyperth.*bullish', r'hyperth.*long', r'hyperth.*buy',
        r'هايبيرث.*صعودي', r'هايبيرث.*شراء', r'vip.*bullish', r'vip.*long', 
        r'premium.*bullish', r'premium.*long'
    ]
    
    for pattern in luxalgo_bearish_patterns:
        if re.search(pattern, signal_lower):
            return "bearish"
    
    for pattern in luxalgo_bullish_patterns:
        if re.search(pattern, signal_lower):
            return "bullish"
    
    # رابعاً: إذا لم يتم التعرف، نعتبرها صعودية كإفتراض آمن
    print("⚠️  Could not determine direction, defaulting to bullish")
    return "bullish"

# ✅ استخراج اسم الإشارة من الرسالة
def extract_signal_name(signal_text):
    """استخراج اسم الإشارة مع الاحتفاظ بالنص الأصلي"""
    signal_lower = signal_text.lower()
    
    # LuxAlgo HyperTH
    if any(term in signal_lower for term in ["hyperth", "hyper_th", "hypert", "هايبيرث", "هيبرث"]):
        if any(term in signal_lower for term in ["bearish", "short", "sell", "هبوطي", "بيع"]):
            return "HYPERTH هبوطي"
        elif any(term in signal_lower for term in ["bullish", "long", "buy", "صعودي", "شراء"]):
            return "HYPERTH صعودي"
        return "HYPERTH"
    
    # LuxAlgo VIP
    if any(term in signal_lower for term in ["vip", "في أي بي", "فاي بي"]):
        if any(term in signal_lower for term in ["bearish", "short", "sell", "هبوطي", "بيع"]):
            return "VIP هبوطي"
        elif any(term in signal_lower for term in ["bullish", "long", "buy", "صعودي", "شراء"]):
            return "VIP صعودي"
        return "VIP"
    
    # LuxAlgo Premium
    if any(term in signal_lower for term in ["premium", "بريميوم"]):
        if any(term in signal_lower for term in ["bearish", "short", "sell", "هبوطي", "بيع"]):
            return "بريميوم هبوطي"
        elif any(term in signal_lower for term in ["bullish", "long", "buy", "صعودي", "شراء"]):
            return "بريميوم صعودي"
        return "بريميوم"
    
    # إرجاع النص الأصلي مختصراً إذا كان طويلاً
    if len(signal_text) > 50:
        return signal_text[:50] + "..."
    return signal_text

def process_alerts(alerts):
    now = datetime.utcnow()
    print(f"🔍 Processing {len(alerts)} alerts")
    
    for alert in alerts:
        try:
            if isinstance(alert, dict):
                signal_text = alert.get("signal", alert.get("message", "")).strip()
                original_direction = alert.get("direction", "").strip()
                ticker = alert.get("ticker", "").strip().upper()
            else:
                signal_text = str(alert).strip()
                original_direction = ""
                ticker = ""
            
            if not signal_text:
                continue
                
            extracted_ticker = extract_symbol(signal_text, ticker)
            if extracted_ticker == "UNKNOWN":
                print(f"⚠️  Could not extract symbol from: {signal_text}")
                continue
            
            # تحديد الاتجاه بدقة عالية
            direction = determine_signal_direction(signal_text, original_direction)
            print(f"🎯 Symbol: {extracted_ticker}, Direction: {direction}, Signal: {signal_text[:50]}...")
            
            if extracted_ticker not in signal_memory:
                signal_memory[extracted_ticker] = {"bullish": [], "bearish": []}
            
            # إنشاء بيانات الإشارة
            signal_data = {
                'text': signal_text,
                'timestamp': now,
                'direction': direction,
                'name': extract_signal_name(signal_text),
                'original_text': signal_text  # حفظ النص الأصلي
            }
            
            # التحقق من التكرار (نفس النص في آخر 5 دقائق)
            cutoff = now - timedelta(minutes=5)
            existing_signals = [
                sig for sig in signal_memory[extracted_ticker][direction] 
                if sig['timestamp'] > cutoff
            ]
            
            existing_texts = [sig['text'].lower() for sig in existing_signals]
            if signal_text.lower() in existing_texts:
                print(f"⚠️  Ignored duplicate signal for {extracted_ticker}")
                continue
            
            # تخزين الإشارة
            signal_memory[extracted_ticker][direction].append(signal_data)
            print(f"✅ Stored {direction} signal for {extracted_ticker}")
            
        except Exception as e:
            print(f"❌ Error processing alert: {e}")
            continue
    
    # تنظيف الإشارات القديمة
    cleanup_signals()
    
    # التحقق من الإشارات المجمعة
    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:
                signal_count = len(signals[direction])
                
                # عرض النصوص الأصلية للإشارات
                signal_details = []
                for i, sig in enumerate(signals[direction], 1):
                    # تقصير النص إذا كان طويلاً
                    display_text = sig['original_text']
                    if len(display_text) > 60:
                        display_text = display_text[:60] + "..."
                    signal_details.append(f"{i}. {display_text}")
                
                saudi_time = get_saudi_time()
                
                if direction == "bullish":
                    message = f"""🚀 <b>{symbol} - تأكيد إشارة صعودية</b>

📊 <b>الإشارات المستلمة:</b>
{chr(10).join(signal_details)}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

⚠️ <b>تنبيه:</b> هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك"""
                else:
                    message = f"""📉 <b>{symbol} - تأكيد إشارة هبوطية</b>

📊 <b>الإشارات المستلمة:</b>
{chr(10).join(signal_details)}

🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

⚠️ <b>تنبيه:</b> هذه ليست نصيحة مالية، قم بإدارة المخاطر الخاصة بك"""
                
                # إرسال التنبيه
                success = send_telegram_to_all(message)
                if success:
                    print(f"🎉 تم إرسال تنبيه {direction} لـ {symbol}")
                    # مسح الإشارات بعد الإرسال الناجح
                    signal_memory[symbol][direction] = []
                else:
                    print(f"❌ فشل إرسال تنبيه {direction} لـ {symbol}")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        
        # محاولة parsing JSON
        if request.is_json:
            try:
                data = request.get_json(force=True)
                if isinstance(data, list):
                    alerts = data
                elif isinstance(data, dict):
                    if "alerts" in data:
                        alerts = data["alerts"]
                    else:
                        alerts = [data]
            except:
                pass
        
        # إذا فشل JSON، استخدام البيانات الخام
        if not alerts:
            raw_data = request.get_data(as_text=True).strip()
            if raw_data:
                alerts = [{"signal": raw_data}]
        
        print(f"📨 Received {len(alerts)} alert(s)")
        
        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "processed", "count": len(alerts)}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200
            
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "active",
        "time": get_saudi_time(),
        "required_signals": REQUIRED_SIGNALS,
        "stocks": STOCK_LIST
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🟢 Server started on port {port}")
    print(f"🔒 Monitoring LuxAlgo signals with high accuracy")
    app.run(host="0.0.0.0", port=port)
