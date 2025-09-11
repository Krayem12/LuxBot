# ✅ نظام منع التكرار الصارم جداً
def is_duplicate_signal(symbol, signal_text, signal_fingerprint):
    """Check if signal is duplicate within the specified timeframe"""
    if symbol not in signal_memory:
        return False
        
    # 1. التحقق من البصمة أولاً (أسرع طريقة)
    last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
    if last_seen:
        time_diff = (datetime.utcnow() - last_seen).total_seconds()
        if time_diff < DUPLICATE_TIMEFRAME:
            print(f"⚠️ Duplicate signal for {symbol} ignored (fingerprint match)")
            return True
    
    # 2. تنظيف الإشارة بشكل مكثف
    current_signal = signal_text.strip()
    
    # إزالة جميع المسافات الزائدة والأحرف الخاصة
    current_clean = re.sub(r'[^\w\s]', '', current_signal.lower())
    current_clean = re.sub(r'\s+', ' ', current_clean).strip()
    
    # 3. إزالة اسم السهم تماماً من المقارنة
    current_without_symbol = re.sub(r'\b' + re.escape(symbol.lower()) + r'\b', '', current_clean)
    current_without_symbol = re.sub(r'\s+', ' ', current_without_symbol).strip()
    
    # 4. إذا كانت الإشارة فارغة بعد إزالة السهم، نستخدم الإشارة الأصلية
    if not current_without_symbol:
        current_without_symbol = current_clean
    
    # 5. البحث في جميع الإشارات المخزنة
    for existing_signal, ts, fp in signal_memory[symbol]["bullish"] + signal_memory[symbol]["bearish"]:
        # تنظيف الإشارة المخزنة بنفس الطريقة
        existing_clean = re.sub(r'[^\w\s]', '', existing_signal.split('_')[0].lower())
        existing_clean = re.sub(r'\s+', ' ', existing_clean).strip()
        
        # إزالة اسم السهم من الإشارة المخزنة
        existing_without_symbol = re.sub(r'\b' + re.escape(symbol.lower()) + r'\b', '', existing_clean)
        existing_without_symbol = re.sub(r'\s+', ' ', existing_without_symbol).strip()
        
        if not existing_without_symbol:
            existing_without_symbol = existing_clean
        
        # المقارنة المباشرة بعد إزالة السهم
        if current_without_symbol == existing_without_symbol and current_without_symbol != "":
            time_diff = (datetime.utcnow() - ts).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ Duplicate signal for {symbol} ignored (same content without symbol)")
                print(f"   Current cleaned: '{current_without_symbol}'")
                print(f"   Existing cleaned: '{existing_without_symbol}'")
                return True
        
        # المقارنة الكاملة مع السهم
        if current_clean == existing_clean:
            time_diff = (datetime.utcnow() - ts).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ Duplicate signal for {symbol} ignored (exact match)")
                return True
    
    return False

# ✅ زيادة وقت المنع إلى 10 دقائق للتأكد
DUPLICATE_TIMEFRAME = 600  # 600 seconds = 10 minutes

# ✅ في دالة process_alerts، إضافة تحقق إضافي
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

        # تنظيف الإشارة من الأحرف غير الإنجليزية
        signal = re.sub(r'[^\x00-\x7F]+', ' ', signal).strip()
        
        # استخراج السهم إذا لم يكن موجودًا
        if not ticker or ticker == "UNKNOWN":
            ticker = extract_symbol(signal)

        if ticker == "UNKNOWN":
            print(f"⚠️ Could not extract symbol from: {signal}")
            continue

        # تحديد الاتجاه تلقائياً من الإشارة
        signal_lower = signal.lower()
        if ("bearish" in signal_lower or "down" in signal_lower or 
            "put" in signal_lower or "short" in signal_lower or
            "downward" in signal_lower or "overbought" in signal_lower):
            direction = "bearish"
        else:
            direction = "bullish"

        # إنشاء بصمة فريدة للإشارة (باستخدام الإشارة الكاملة)
        signal_type = extract_signal_type(signal)
        signal_fingerprint = create_signal_fingerprint(signal, ticker, direction)
        
        # التحقق من التكرار (باستخدام النظام الجديد الصارم)
        if is_duplicate_signal(ticker, signal, signal_fingerprint):
            print(f"⏩ Skipping duplicate signal: {signal}")
            continue

        # تخزين الإشارة
        if ticker not in signal_memory:
            signal_memory[ticker] = {"bullish": [], "bearish": [], "last_signals": {}}

        # تحديث وقت آخر رؤية لهذه البصمة
        signal_memory[ticker]["last_signals"][signal_fingerprint] = now
        
        unique_key = f"{signal}_{now.timestamp()}"
        signal_memory[ticker][direction].append((unique_key, now, signal_fingerprint))
        print(f"✅ Stored {direction} signal for {ticker}: {signal}")

    # تنظيف الإشارات القديمة
    cleanup_signals()

    # التحقق من إشارات كل سهم - إشارتان على الأقل
    for symbol, signals in signal_memory.items():
        for direction in ["bullish", "bearish"]:
            if len(signals[direction]) >= REQUIRED_SIGNALS:
                signal_count = len(signals[direction])
                
                # الحصول على التوقيت السعودي
                saudi_time = get_saudi_time()
                
                # بناء قائمة الإشارات المستلمة (بدون أرقام وطوابع زمنية)
                signals_list = "\n".join([f"{i+1}. {clean_signal_name(sig[0])}" for i, sig in enumerate(signals[direction])])
                
                if direction == "bullish":
                    message = f"""🚀 <b>{symbol} - Bullish Signal Confirmation</b>

📊 <b>Received Signals:</b>
{signals_list}

🔢 <b>Signals Count:</b> {signal_count}
⏰ <b>Saudi Time:</b> {saudi_time}

⚠️ <i>Warning: This is not financial advice, manage your own risks</i>"""
                    signal_type = "BULLISH_CONFIRMATION"
                else:
                    message = f"""📉 <b>{symbol} - Bearish Signal Confirmation</b>

📊 <b>Received Signals:</b>
{signals_list}

🔢 <b>Signals Count:</b> {signal_count}
⏰ <b>Saudi Time:</b> {saudi_time}

⚠️ <i>Warning: This is not financial advice, manage your own risks</i>"""
                    signal_type = "BEARISH_CONFIRMATION"
                
                # إرسال إلى التليجرام
                telegram_success = send_telegram_to_all(message)
                
                # إرسال إلى الخادم الخارجي
                external_success = send_post_request(message, f"{direction.upper()} signals", signal_type)
                
                if telegram_success and external_success:
                    print(f"🎉 Alert sent successfully for {symbol}")
                elif telegram_success and not external_success:
                    print(f"⚠️ Telegram sent but external server failed for {symbol}")
                else:
                    print(f"❌ Complete send failure for {symbol}")
                
                # مسح الإشارات بعد الإرسال
                signal_memory[symbol][direction] = []
                print(f"📤 Sent alert for {symbol} ({direction})")
            if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
else:
    application = app
