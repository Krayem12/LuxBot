# ✅ نظام منع التكرار الصارم
def is_duplicate_signal(symbol, signal_text, signal_fingerprint):
    """Check if signal is duplicate within the specified timeframe"""
    if symbol not in signal_memory:
        return False
        
    # التحقق من البصمة أولاً (أسرع طريقة)
    last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
    if last_seen:
        time_diff = (datetime.utcnow() - last_seen).total_seconds()
        if time_diff < DUPLICATE_TIMEFRAME:
            print(f"⚠️ Duplicate signal for {symbol} ignored (fingerprint match, diff: {time_diff:.1f}s)")
            return True
    
    # تنظيف الإشارة الحالية بشكل كامل ومكثف
    current_signal = signal_text.strip()
    
    # إزالة جميع المسافات الزائدة والأحرف الخاصة
    current_clean = re.sub(r'[^\w\s]', '', current_signal.lower())  # إزالة الرموز
    current_clean = re.sub(r'\s+', ' ', current_clean).strip()  # إزالة المسافات الزائدة
    
    # إزالة اسم السهم تماماً من المقارنة
    current_without_symbol = re.sub(r'\b' + re.escape(symbol.lower()) + r'\b', '', current_clean)
    current_without_symbol = re.sub(r'\s+', ' ', current_without_symbol).strip()
    
    # إذا كانت الإشارة فارغة بعد إزالة السهم، نستخدم الإشارة الأصلية
    if not current_without_symbol:
        current_without_symbol = current_clean
    
    # البحث في جميع الإشارات المخزنة لهذا السهم
    for existing_signal, ts, fp in signal_memory[symbol]["bullish"] + signal_memory[symbol]["bearish"]:
        # تنظيف الإشارة المخزنة بنفس الطريقة
        existing_clean = re.sub(r'[^\w\s]', '', existing_signal.split('_')[0].lower())
        existing_clean = re.sub(r'\s+', ' ', existing_clean).strip()
        
        # إزالة اسم السهم من الإشارة المخزنة
        existing_without_symbol = re.sub(r'\b' + re.escape(symbol.lower()) + r'\b', '', existing_clean)
        existing_without_symbol = re.sub(r'\s+', ' ', existing_without_symbol).strip()
        
        if not existing_without_symbol:
            existing_without_symbol = existing_clean
        
        # 1. المقارنة المباشرة بعد إزالة السهم (أكثر صرامة)
        if current_without_symbol == existing_without_symbol and current_without_symbol != "":
            time_diff = (datetime.utcnow() - ts).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ Duplicate signal for {symbol} ignored (same content without symbol)")
                print(f"   Cleaned: '{current_without_symbol}'")
                return True
        
        # 2. المقارنة الكاملة مع السهم
        if current_clean == existing_clean:
            time_diff = (datetime.utcnow() - ts).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ Duplicate signal for {symbol} ignored (exact match)")
                return True
        
        # 3. مقارنة الكلمات الرئيسية (إذا كانت 90% من الكلمات متشابهة)
        current_words = set(current_clean.split())
        existing_words = set(existing_clean.split())
        
        if current_words and existing_words:
            common_words = current_words.intersection(existing_words)
            similarity_ratio = len(common_words) / max(len(current_words), len(existing_words))
            
            if similarity_ratio >= 0.9:  # 90% تشابه
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"⚠️ Similar signal for {symbol} ignored ({similarity_ratio:.0%} similarity)")
                    print(f"   Common words: {common_words}")
                    return True
    
    return False

# ✅ في دالة process_alerts، تأكد من أن الإشارة تُخزن بشكل صحيح
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

        # إنشاء بصمة فريدة للإشارة
        signal_type = extract_signal_type(signal)
        signal_fingerprint = create_signal_fingerprint(signal, ticker, direction)  # استخدام الإشارة الكاملة هنا
        
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
