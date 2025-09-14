# في دالة process_confirmation_signals، أضف معالجة للحالة عندما لا يكون هناك اتجاه عام
def process_confirmation_signals(symbol, direction):
    signals = signal_memory[symbol][direction]
    
    if len(signals) >= REQUIRED_CONFIRMATION_SIGNALS:
        saudi_time = get_saudi_time()
        signal_count = len(signals)
        
        # Get the clean signal name from the latest signal
        latest_signal, latest_ts = signals[-1]
        clean_signal = extract_clean_signal_name(latest_signal)
        
        # Check if confirmation matches current trend OR if no trend is set yet
        if (last_trend_direction is None) or \
           (direction == "bullish" and last_trend_direction == "bullish") or \
           (direction == "bearish" and last_trend_direction == "bearish"):
            
            if direction == "bullish":
                if last_trend_direction == "bullish":
                    trend_text = "مع الاتجاه العام - متوقع حركة صعودية"
                else:
                    trend_text = "إشارة صعودية - مراقبة الأداء"
                
                message = f"""🚀 <b>{symbol} - تأكيد دخول صعودي</b>

🎯 <b>الإشارة التأكيدية:</b> {clean_signal}
🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>{trend_text}</code>"""
            else:
                if last_trend_direction == "bearish":
                    trend_text = "مع الاتجاه العام - متوقع حركة هبوطية"
                else:
                    trend_text = "إشارة هبوطية - مراقبة الأداء"
                
                message = f"""📉 <b>{symbol} - تأكيد دخول هبوطي</b>

🎯 <b>الإشارة التأكيدية:</b> {clean_signal}
🔢 <b>عدد الإشارات:</b> {signal_count}
⏰ <b>التوقيت السعودي:</b> {saudi_time}

<code>{trend_text}</code>"""
            
            telegram_success = send_telegram_to_all(message)
            external_success = send_post_request(message, "CONFIRMATION_SIGNALS", 
                                               "BULLISH_CONFIRMATION" if direction == "bullish" else "BEARISH_CONFIRMATION")
            
            if telegram_success:
                print(f"🎉 Confirmation alert sent for {symbol} ({direction})")
            
            # Clear confirmation signals after sending
            signal_memory[symbol][direction] = []
            return True
    
    return False
