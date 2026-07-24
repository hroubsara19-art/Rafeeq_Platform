"""
اختبار بسيط لـ Azure Speech Service
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from learning.utils import generate_audio_azure

# نص تجريبي
test_text = "مرحباً بك في منصة رفيق. هذا اختبار لتوليد الصوت باستخدام Azure Speech Service."

# مسار الملف
test_audio_path = "lessons/audio/test_azure.mp3"

print("جاري اختبار Azure Speech Service...")
print(f"النص: {test_text}")

try:
    timing_path = generate_audio_azure(test_text, test_audio_path)
    if timing_path:
        print(f"✅ نجح الاختبار!")
        print(f"مسار الصوت: {test_audio_path}")
        print(f"مسار التوقيت: {timing_path}")
    else:
        print("❌ فشل الاختبار - لم يتم إرجاع مسار التوقيت")
except Exception as e:
    print(f"❌ حدث خطأ: {str(e)}")
