"""
learning/encryption.py
═══════════════════════
وحدة تشفير مركزية لمفاتيح API باستخدام Fernet (AES-128-CBC).

الاستخدام:
    from learning.encryption import encrypt_api_key, decrypt_api_key

    # حفظ
    teacher.gemini_api_key = encrypt_api_key(raw_key)
    teacher.save()

    # قراءة
    raw_key = decrypt_api_key(teacher.gemini_api_key)

متطلبات:
    pip install cryptography

متغير البيئة المطلوب في .env:
    API_ENCRYPTION_KEY=<ناتج python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

[FIX] decrypt_api_key الآن يتحقق من is_encrypted() أولاً قبل محاولة الفك.
      السبب: بعض المفاتيح في القاعدة محفوظة كنص عادي (غير مشفّر) بسبب
      تعديل يدوي مباشر، وكانت كل قراءة لها تُطلق exception + warning
      رغم أن هذا سلوك متوقّع وليس خطأً فعلياً. الآن الـ warning يظهر
      فقط إذا كانت القيمة تبدو مشفّرة (تبدأ بـ gAAA) لكن فشل فكها فعلاً
      — وهذا مؤشر مشكلة حقيقية (مثلاً تغيّر API_ENCRYPTION_KEY).
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# ── جلب مفتاح التشفير ──────────────────────────────────────────
def _get_fernet():
    """
    يُعيد كائن Fernet جاهزاً للاستخدام.
    يقرأ المفتاح من settings.API_ENCRYPTION_KEY (ويأتي من .env).
    يُسجّل خطأ واضحاً إذا لم يُضبَط المفتاح.
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise RuntimeError(
            "مكتبة cryptography غير مثبّتة.\n"
            "نفّذ: pip install cryptography"
        )

    key = getattr(settings, 'API_ENCRYPTION_KEY', None)
    if not key:
        raise ValueError(
            "API_ENCRYPTION_KEY غير محدد في settings/env.\n"
            "أنشئ مفتاحاً بـ: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "ثم أضفه في .env: API_ENCRYPTION_KEY=<المفتاح>"
        )

    if isinstance(key, str):
        key = key.encode()

    return Fernet(key)


# ── دوال التشفير والفك ─────────────────────────────────────────

def encrypt_api_key(raw_key: str) -> str:
    """
    يُشفّر مفتاح API ويُعيده كنص base64.
    يُعيد سلسلة فارغة إذا كان المدخل فارغاً.
    """
    if not raw_key or not raw_key.strip():
        return ''
    try:
        f = _get_fernet()
        return f.encrypt(raw_key.strip().encode()).decode()
    except Exception as e:
        logger.error(f"encrypt_api_key failed: {e}")
        raise


def is_encrypted(value: str) -> bool:
    """يتحقق إذا كانت القيمة مُشفَّرة بـ Fernet (تبدأ بـ gAAA)."""
    return bool(value and value.startswith('gAAA'))


def decrypt_api_key(encrypted_key: str) -> str:
    """
    يفكّ تشفير مفتاح API.

    - إذا كانت القيمة فارغة → يُعيد سلسلة فارغة.
    - إذا كانت القيمة غير مُشفّرة أصلاً (لا تبدأ بـ gAAA، مثل مفاتيح
      محفوظة يدوياً كنص عادي) → يُعيدها كما هي مباشرة، بدون محاولة فك
      وبدون أي warning (هذا سلوك متوقَّع وليس خطأً).
    - إذا كانت تبدو مُشفّرة (تبدأ بـ gAAA) لكن فشل فكها فعلاً → هذا خطأ
      حقيقي (مثلاً API_ENCRYPTION_KEY تغيّر)، فيُسجَّل warning ويُعاد
      النص كما هو كتراجع آمن.
    """
    if not encrypted_key or not encrypted_key.strip():
        return ''

    value = encrypted_key.strip()

    # ✅ [FIX] فحص مسبق: قيمة غير مشفّرة أصلاً → رجّعها فوراً بدون ضجيج
    if not is_encrypted(value):
        logger.debug(
            f"decrypt_api_key: plain (unencrypted) value detected, "
            f"returning as-is: {value[:8]}..."
        )
        return value

    try:
        f = _get_fernet()
        return f.decrypt(value.encode()).decode()
    except Exception as e:
        # الآن هذا warning ذو معنى فعلي: القيمة تبدو مشفّرة لكن فشل فكها
        logger.warning(
            f"decrypt_api_key failed on what looked like encrypted "
            f"(gAAA-prefixed) data: {e}"
        )
        return value