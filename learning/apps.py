import subprocess
import sys
import os
from django.apps import AppConfig


class LearningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'learning'

    def ready(self):
        # تشغيل خادم الانتباه تلقائياً عند بدء Django
        if os.environ.get('RUN_MAIN') == 'true':  # تجنب التشغيل المزدوج مع auto-reload
            try:
                subprocess.Popen(
                    [sys.executable, '-m', 'uvicorn',
                     'fastapi_server:app',
                     '--host', '0.0.0.0',
                     '--port', '5051',
                     '--log-level', 'warning'],
                    cwd=r'C:\Users\Shaheen\adhd_learning_system\attention_tracker',
                    creationflags=subprocess.CREATE_NO_WINDOW  # Windows فقط
                )
                print("✅ خادم الانتباه يعمل تلقائياً على http://localhost:5051")
            except Exception as e:
                print(f"⚠️ فشل تشغيل خادم الانتباه تلقائياً: {e}")
