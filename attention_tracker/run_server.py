"""
سكريبت بسيط لتشغيل خادم Flask بدون مشاكل colorama
"""
import os
import sys

# تعطيل colorama قبل أي استيراد آخر
os.environ['NO_COLOR'] = '1'
os.environ['TERM'] = 'dumb'

# تعطيل reloader لتجنب المشاكل
sys.argv = [sys.argv[0], '--no-reload']

from werkzeug.serving import make_server
from flask_server import app, logger

if __name__ == '__main__':
    logger.info("🚀 خادم تتبع الانتباه يعمل على http://localhost:5050")
    try:
        server = make_server('0.0.0.0', 5050, app, threaded=True)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("تم إيقاف الخادم")
    except Exception as e:
        logger.error(f"خطأ في تشغيل الخادم: {e}")
