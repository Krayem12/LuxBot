# اختبار خدمتي التليجرام والخادم الخارجي
def test_services():
    print("Testing services...")
    
    # اختبار التليجرام - إرسال رسالة تجريبية
    telegram_result = send_telegram_to_all("🔧 Test message from bot - System is working!")
    print(f"Telegram test result: {telegram_result}")
    
    # اختبار الخادم الخارجي - إرسال بيانات تجريبية
    external_result = send_post_request("Test message", "TEST_SIGNAL", "BULLISH_CONFIRMATION")
    print(f"External API test result: {external_result}")
    
    return telegram_result and external_result

# إعدادات الوقت السعودي (UTC+3)
TIMEZONE_OFFSET = 3

# الحصول على التوقيت السعودي
def get_saudi_time():
    return (datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)).strftime('%H:%M:%S')

# إزالة تنسيق HTML من النص
def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# إرسال رسالة إلى التليجرام
def send_telegram_to_all(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # إرسال الطلب مع timeout قصير
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
            
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# تحميل قائمة الأسهم من ملف
def load_stocks():
    stocks = []
    try:
        with open('stocks.txt', 'r') as f:
            stocks = [line.strip().upper() for line in f if line.strip()]
    except FileNotFoundError:
        stocks = ["BTCUSDT", "ETHUSDT", "SPX500", "NASDAQ100", "US30"]
    return stocks

# إرسال طلب POST إلى الخادم الخارجي
def send_post_request(message, indicators, signal_type=None):
    url = "https://backend-thrumming-moon-2807.fly.dev/sendMessage"
    
    # تنظيف الرسالة من HTML
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
        return response.status_code == 200
            
    except Exception as e:
        print(f"External API error: {e}")
        return False

# تنظيف الإشارات القديمة (أكثر من 15 دقيقة)
def cleanup_signals():
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    for symbol in list(signal_memory.keys()):
        for direction in ["bullish", "bearish"]:
            signal_memory[symbol][direction] = [
                (sig, ts) for sig, ts in signal_memory[symbol][direction] 
                if ts > cutoff
            ]

# استخراج اسم السهم من الرسالة
def extract_symbol(message):
    message_upper = message.upper()
    
    # البحث عن الرموز في القائمة
    sorted_stocks = sorted(STOCK_LIST, key=len, reverse=True)
    for symbol in sorted_stocks:
        if symbol in message_upper:
            return symbol
    
    # البحث عن أنماط معروفة
    if "SPX" in message_upper or "500" in message_upper:
        return "SPX500"
    elif "BTC" in message_upper:
        return "BTCUSDT" 
    # ... وغيرها من الرموز
    
    return "SPX500"  # افتراضي

# استخراج اسم الإشارة نظيف بدون أرقام
def extract_clean_signal_name(raw_signal):
    # إزالة الطوابع الزمنية والأرقام
    clean_signal = re.sub(r'_\d+\.\d+', '', raw_signal)
    clean_signal = re.sub(r'\b\d+\b', '', clean_signal)
    clean_signal = re.sub(r'\s+', ' ', clean_signal).strip()
    return clean_signal if clean_signal else raw_signal

# معالجة التنبيهات الواردة
def process_alerts(alerts):
    now = datetime.utcnow()
    print(f"Processing {len(alerts)} alerts")

    for alert in alerts:
        # معالجة كل تنبيه وتخزينه
        # ... كود المعالجة

# تسجيل معلومات الطلبات الواردة (للتdebug)
@app.before_request
def log_request_info():
    if request.path == '/webhook':
        print(f"\nIncoming request: {request.method} {request.path}")
        print(f"Content-Type: {request.content_type}")

# استقبال webhook من TradingView
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        alerts = []
        # معالجة البيانات الواردة
        # ... كود الاستقبال
        
        if alerts:
            process_alerts(alerts)
            return jsonify({"status": "alert_processed"}), 200
        else:
            return jsonify({"status": "no_alerts"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# الصفحة الرئيسية للفحص
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "TradingView Webhook Receiver is active",
        "monitored_stocks": STOCK_LIST
    })

# تشغيل التطبيق
if __name__ == "__main__":
    # اختبار الخدمات أولاً
    test_services()
    
    port = int(os.environ.get("PORT", 10000))
    print(f"Server started on port {port}")
    app.run(host="0.0.0.0", port=port)
