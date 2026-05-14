"""
سكريبت بسيط لتشغيل خادم FastAPI بدون مشاكل colorama
"""
import os
import sys

# تعطيل colorama قبل أي استيراد آخر
os.environ['NO_COLOR'] = '1'
os.environ['TERM'] = 'dumb'

import uvicorn
from fastapi_server import app, logger

if __name__ == '__main__':
    logger.info("🚀 خادم تتبع الانتباه يعمل على http://localhost:5050")
    try:
        uvicorn.run(app, host="0.0.0.0", port=5050)
    except KeyboardInterrupt:
        logger.info("تم إيقاف الخادم")
    except Exception as e:
        logger.error(f"خطأ في تشغيل الخادم: {e}")
