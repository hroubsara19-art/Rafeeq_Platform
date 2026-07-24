"""
اختبار بسيط لـ Azure Speech Service بدون Django
"""
import azure.cognitiveservices.speech as speechsdk
import os

# إعدادات Azure (قراءة من متغيّرات البيئة بأمان لتفادي حظر GitHub)
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "YOUR_AZURE_KEY_HERE")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")  # ضع الـ region الخاصة بك هنا

# نص تجريبي
test_text = "مرحباً بك في منصة رفيق. هذا اختبار لتوليد الصوت باستخدام Azure Speech Service."

print("جاري اختبار Azure Speech Service...")
print(f"النص: {test_text}")

try:
    # إعداد Azure Speech
    speech_config = speechsdk.SpeechConfig(
        subscription=SPEECH_KEY,
        region=SPEECH_REGION
    )
    speech_config.speech_synthesis_voice_name = "ar-SA-HamedNeural"
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )

    audio_config = speechsdk.audio.AudioOutputConfig(filename="test_azure.mp3")
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config
    )

    words_timestamps = []

    # معالج WordBoundary
    def word_boundary_handler(evt):
        start_time = evt.audio_offset / 10000000.0
        duration = evt.duration.total_seconds()
        words_timestamps.append({
            "word": evt.text,
            "start": round(start_time, 3),
            "end": round(start_time + duration, 3)
        })
        print(f"Word: {evt.text} | Start: {start_time:.3f}s | End: {start_time + duration:.3f}s")

    synthesizer.synthesis_word_boundary.connect(word_boundary_handler)

    # توليد الصوت
    print("جاري توليد الصوت...")
    result = synthesizer.speak_text_async(test_text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(f"✅ نجح الاختبار!")
        print(f"تم توليد {len(words_timestamps)} كلمة مع توقيتات")
        print(f"تم حفظ الملف: test_azure.mp3")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"❌ فشل الاختبار: {result.reason}")
        print(f"سبب الإلغاء: {cancellation_details.reason}")
        print(f"تفاصيل الخطأ: {cancellation_details.error_details}")
    else:
        print(f"❌ فشل الاختبار: {result.reason}")

except Exception as e:
    print(f"❌ حدث خطأ: {str(e)}")
    import traceback
    traceback.print_exc()