from difflib import SequenceMatcher

# ✅ دالة حساب التشابه بين النصوص
def similar(a, b):
    """حساب نسبة التشابه بين نصين"""
    return SequenceMatcher(None, a, b).ratio()

# ✅ التحقق من التكرار (معدل بشكل أقوى)
def is_duplicate_signal(symbol, signal_text, signal_fingerprint):
    """التحقق مما إذا كانت الإشارة مكررة خلال الفترة الزمنية المحددة"""
    if symbol in signal_memory:
        # التحقق من البصمة أولاً
        last_seen = signal_memory[symbol]["last_signals"].get(signal_fingerprint)
        if last_seen:
            time_diff = (datetime.utcnow() - last_seen).total_seconds()
            if time_diff < DUPLICATE_TIMEFRAME:
                print(f"⚠️ إشارة مكررة لـ {symbol} تم تجاهلها (الفارق: {time_diff:.1f} ثانية)")
                return True
        
        # التحقق من المحتوى المشابه أيضاً (نفس السهم ونفس النص تقريباً)
        signal_lower = signal_text.lower().strip()
        for existing_signal, ts, fp in signal_memory[symbol]["bullish"] + signal_memory[symbol]["bearish"]:
            existing_lower = existing_signal.lower().strip()
            
            # إذا كانت الإشارة متشابهة بنسبة 90% أو أكثر
            similarity = similar(signal_lower, existing_lower)
            if similarity > 0.9:
                time_diff = (datetime.utcnow() - ts).total_seconds()
                if time_diff < DUPLICATE_TIMEFRAME:
                    print(f"⚠️ إشارة متشابهة لـ {symbol} تم تجاهلها (التشابه: {similarity:.1%}, الفارق: {time_diff:.1f} ثانية)")
                    return True
    
    return False

# ✅ في دالة process_alerts (تعديل جزء التحقق من التكرار)
# تغيير هذا السطر:
if is_duplicate_signal(ticker, signal_fingerprint):
# إلى:
if is_duplicate_signal(ticker, signal, signal_fingerprint):
