"""
learning/utils.py
═════════════════
منشئ الدروس الذكي — منصة رفيق ADHD Platform

الإصلاحات:
  ✅ خريطة تصحيح الموديلات: gemini-1.5-flash → gemini-1.5-flash-002
  ✅ أولوية الموديلات: gemini-2.5-flash أولاً (مجاني ومدعوم)
  ✅ نفس منطق _get_api_key من chat_views الناجح (env أولاً)
  ✅ generate_audio_async: stream صحيح لجمع WordBoundary
  ✅ timing JSON للتظليل كلمة بكلمة
  ✅ [JSON-FIX] _sanitize_json_str: يُصلح \\n الخام داخل قيم paragraph
     السبب: Gemini أحياناً يُرجع أسطراً خام داخل "paragraph": "..."
     مما يُسبب "Invalid control character" في json.loads وفشل التوليد
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import re
import time

import edge_tts
import azure.cognitiveservices.speech as speechsdk
from django.conf import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# خريطة تصحيح أسماء الموديلات
# ══════════════════════════════════════════════════════════════
_MODEL_FIX = {
    # الأسماء الناقصة → الأسماء الكاملة الصحيحة
    'gemini-1.5-flash':       'gemini-1.5-flash-002',
    'gemini-1.5-flash-001':   'gemini-1.5-flash-001',
    'gemini-1.5-pro':         'gemini-1.5-pro-002',
    'gemini-2.0-flash':       'gemini-2.0-flash-001',
    'gemini-2.5-flash':       'gemini-2.5-flash',          # مدعوم مباشرة
    'gemini-2.5-pro':         'gemini-2.5-pro',
    'gemini-2.0-flash-lite':  'gemini-2.0-flash-lite',
}

_VALID_MODELS = {
    'gemini-2.5-flash',
    'gemini-2.5-flash-preview-05-20',
    'gemini-2.5-pro',
    'gemini-2.0-flash-001',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash-002',
    'gemini-1.5-flash-001',
    'gemini-1.5-pro-002',
    'gemini-1.5-flash-8b',
}

# ✅ الأولوية: 2.5-flash أولاً (مجاني) ثم 2.0 ثم 1.5
_DEFAULT_MODEL  = 'gemini-2.5-flash'
_FALLBACK_CHAIN = ['gemini-2.5-flash', 'gemini-1.5-flash-002', 'gemini-2.0-flash-001']

_GEMINI_REST = (
    'https://generativelanguage.googleapis.com'
    '/v1beta/models/{model}:generateContent?key={key}'
)


# ══════════════════════════════════════════════════════════════
# تنظيف اسم الموديل
# ══════════════════════════════════════════════════════════════
def _normalize_model(version: str) -> str:
    if not version:
        return _DEFAULT_MODEL

    v = str(version).strip()

    # إزالة prefix models/
    for pfx in ('models/', 'model/'):
        if v.startswith(pfx):
            v = v[len(pfx):]
            break

    # خريطة التصحيح أولاً
    if v in _MODEL_FIX:
        fixed = _MODEL_FIX[v]
        if fixed != v:
            logger.info(f'[utils] model fix: {version!r} → {fixed!r}')
        return fixed

    # تطابق مباشر
    if v in _VALID_MODELS:
        return v

    # مطابقة جزئية
    for valid in sorted(_VALID_MODELS, key=len, reverse=True):
        if v.startswith(valid.rsplit('-', 1)[0]):
            logger.info(f'[utils] model partial match: {version!r} → {valid!r}')
            return valid

    logger.warning(f'[utils] Unknown model {version!r} → {_DEFAULT_MODEL}')
    return _DEFAULT_MODEL


# ══════════════════════════════════════════════════════════════
# [JSON-FIX] تنظيف JSON الذي يحتوي أسطراً خام داخل strings
# ══════════════════════════════════════════════════════════════
def _sanitize_json_str(s: str) -> str:
    """
    يُصلح JSON الذي يحتوي أسطراً خام (\n حقيقية) ورجوع السطر (\r) أو \t داخل قيم string.

    الحل: معالجة صحيحة للهروب (escaped characters) واستبدال الأحرف التحكمية الخام (Control Characters)
    بمسافات داخل النصوص لمنع خطأ Invalid control character في json.loads.
    """
    result = []
    in_string = False
    i = 0
    length = len(s)

    while i < length:
        c = s[i]

        # التعامل مع الـ Escape sequences القائمة بالفعل
        if c == '\\' and i + 1 < length:
            result.append(c)
            result.append(s[i + 1])
            i += 2
            continue

        # تبديل حالة التواجد داخل نص string أو خارجه
        if c == '"':
            in_string = not in_string
            result.append(c)
            i += 1
            continue

        # استبدال رموز التحكم والأسطر الخام داخل النصوص بمسافات
        if in_string:
            if c in ('\n', '\r', '\t'):
                result.append(' ')
            elif ord(c) < 32:  # التعامل مع باقي Control characters غير المطبوعة
                result.append(' ')
            else:
                result.append(c)
        else:
            result.append(c)

        i += 1

    return ''.join(result)


# ══════════════════════════════════════════════════════════════
# جلب مفتاح API — نفس منطق chat_views الناجح
# ══════════════════════════════════════════════════════════════
def _resolve_api_key(agent_data=None, teacher=None) -> tuple[str, str]:
    """
    ترتيب الأولوية:
      1. GEMINI_API_KEY من settings / .env  ← دائماً أولاً
      2. agent_data المُمرَّر (get_api_key أو raw)
      3. أول AiAgent نشط في DB
      4. مفتاح المعلم الشخصي
    """

    # ── 1. settings / .env ────────────────────────────────────
    env_key = ''
    try:
        env_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    except Exception:
        pass
    if not env_key:
        env_key = os.environ.get('GEMINI_API_KEY', '')

    if env_key and str(env_key).strip().startswith('AIza'):
        key = str(env_key).strip()
        model = _DEFAULT_MODEL
        try:
            if agent_data:
                model = _normalize_model(getattr(agent_data, 'version', '') or '')
        except Exception:
            pass
        logger.info(f'[utils] ✓ GEMINI_API_KEY from env, model={model!r}')
        return key, model

    # ── 2. agent_data المُمرَّر ──────────────────────────────
    if agent_data:
        fn = getattr(agent_data, 'get_api_key', None)
        if fn and callable(fn):
            try:
                k = fn()
                if k and str(k).strip().startswith('AIza'):
                    model = _normalize_model(getattr(agent_data, 'version', '') or '')
                    logger.info(f'[utils] ✓ agent.get_api_key(), model={model!r}')
                    return str(k).strip(), model
            except Exception as e:
                logger.debug(f'[utils] get_api_key() failed: {e}')

        raw = str(getattr(agent_data, 'api_key', '') or '').strip()
        if raw.startswith('AIza'):
            model = _normalize_model(getattr(agent_data, 'version', '') or '')
            logger.info(f'[utils] ✓ agent.api_key raw, model={model!r}')
            return raw, model

    # ── 3. DB AiAgent ─────────────────────────────────────────
    try:
        from learning.models import AiAgent
        agent = AiAgent.objects.filter(isactive=True).first()
        if agent:
            fn = getattr(agent, 'get_api_key', None)
            if fn and callable(fn):
                try:
                    k = fn()
                    if k and str(k).strip():
                        key = str(k).strip()
                        if key.startswith('AIza') or key.startswith('AQ.') or len(key) >= 20:
                            model = _normalize_model(getattr(agent, 'version', '') or '')
                            logger.info(f'[utils] ✓ DB AiAgent.get_api_key(), model={model!r}')
                            return key, model
                except Exception:
                    pass

            raw = str(getattr(agent, 'api_key', '') or '').strip()
            if raw.startswith('AIza') or raw.startswith('AQ.') or len(raw) >= 20:
                model = _normalize_model(getattr(agent, 'version', '') or '')
                logger.info(f'[utils] ✓ DB AiAgent raw, model={model!r}')
                return raw, model
    except Exception as e:
        logger.warning(f'[utils] DB AiAgent lookup failed: {e}')

    # ── 4. مفتاح المعلم ──────────────────────────────────────
    if teacher:
        fn = getattr(teacher, 'get_gemini_key', None)
        if fn and callable(fn):
            try:
                k = fn()
                if k and str(k).strip():
                    key = str(k).strip()
                    if key.startswith('AIza') or key.startswith('AQ.') or len(key) >= 20:
                        logger.info('[utils] ✓ Teacher personal key')
                        return key, _DEFAULT_MODEL
            except Exception:
                pass
        raw = str(getattr(teacher, 'gemini_api_key', '') or '').strip()
        if raw.startswith('AIza') or raw.startswith('AQ.') or len(raw) >= 20:
            logger.info('[utils] ✓ Teacher raw key')
            return raw, _DEFAULT_MODEL

    logger.error('[utils] ✗ No valid Gemini API key found')
    raise ValueError(
        'مفتاح Gemini API غير متاح.\n'
        'الحل: أضف GEMINI_API_KEY=AIza... في ملف .env\n'
        'أو شغّل: python manage.py set_api_key YOUR_KEY'
    )


# ══════════════════════════════════════════════════════════════
# استدعاء Gemini عبر SDK
# ══════════════════════════════════════════════════════════════
def _call_gemini_sdk(api_key: str, model: str, instruction: str, content: str) -> str | None:
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=instruction,
            max_output_tokens=4096,
            temperature=0.7,
            top_p=0.9,
        )
        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role='user', parts=[types.Part(text=content)])],
            config=config,
        )
        text = getattr(response, 'text', None)
        if text:
            logger.info(f'[utils] SDK ✓ model={model!r}')
            return text.strip()
        return None
    except ImportError:
        logger.debug('[utils] google-genai not installed → REST')
        return None
    except Exception as e:
        logger.error(f'[utils] SDK error model={model!r}: {e}')
        return None


# ══════════════════════════════════════════════════════════════
# استدعاء Gemini عبر REST مع fallback chain
# ══════════════════════════════════════════════════════════════
def _call_gemini_rest(api_key: str, model: str, instruction: str,
                      content: str, _tried: set | None = None) -> str | None:
    import urllib.request
    import urllib.error

    if _tried is None:
        _tried = set()
    _tried.add(model)

    url = _GEMINI_REST.format(model=model, key=api_key)
    payload = {
        'system_instruction': {'parts': [{'text': instruction}]},
        'contents':           [{'role': 'user', 'parts': [{'text': content}]}],
        'generationConfig':   {'maxOutputTokens': 4096, 'temperature': 0.7, 'topP': 0.9},
    }
    data = _json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req  = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = _json.loads(resp.read().decode('utf-8'))
        candidates = result.get('candidates', [])
        if not candidates:
            return None
        finish = candidates[0].get('finishReason', '')
        if finish in ('SAFETY', 'RECITATION'):
            logger.warning(f'[utils] REST blocked ({finish})')
            return None
        parts = candidates[0].get('content', {}).get('parts', [])
        text  = parts[0].get('text', '').strip() if parts else ''
        if text:
            logger.info(f'[utils] REST ✓ model={model!r}')
        return text or None

    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='ignore')[:300]
        logger.error(f'[utils] REST HTTP {exc.code} model={model}: {body}')

        # ✅ عند 404 أو 429 → جرّب الموديل التالي في الـ chain
        if exc.code in (400, 404, 429):
            for next_model in _FALLBACK_CHAIN:
                if next_model not in _tried:
                    logger.info(f'[utils] Fallback {exc.code} → {next_model!r}')
                    return _call_gemini_rest(api_key, next_model, instruction, content, _tried)
        return None

    except Exception as exc:
        logger.error(f'[utils] REST error: {exc}')
        return None


def _call_gemini(api_key: str, model: str, instruction: str, content: str) -> str | None:
    """SDK أولاً ثم REST مع fallback chain كامل."""
    logger.info(f'[utils] → model={model!r} key={api_key[:8]}...')

    result = _call_gemini_sdk(api_key, model, instruction, content)
    if result:
        return result

    logger.info('[utils] SDK failed → REST')
    return _call_gemini_rest(api_key, model, instruction, content)


# ══════════════════════════════════════════════════════════════
# توليد الصوت + ملف Timing للتظليل
# ══════════════════════════════════════════════════════════════
async def generate_audio_async(text: str, file_path: str) -> str | None:
    """
    يولّد MP3 + JSON timing للتظليل كلمة بكلمة.
    يستخدم Azure Speech أولاً إذا كان متاحاً، ثم edge_tts كـ fallback.

    Returns:
        مسار ملف timing النسبي (file_path + '.json') أو None.

    بنية timing JSON:
        [{"word": "كلمة", "start": 0.500, "end": 0.850, "char_offset": 0, "char_length": 4}, ...]
    """
    # ✅ محاولة Azure Speech أولاً
    azure_timing = generate_audio_azure(text, file_path)
    if azure_timing:
        logger.info('[utils] Using Azure Speech for audio generation')
        return azure_timing

    # ✅ Fallback إلى edge_tts
    logger.info('[utils] Falling back to edge_tts')
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    # ── تنظيف النص ─────────────────────────────────────────
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'[*#_~`\\]', '', clean)
    clean = re.sub(r'-{2,}', ' ', clean)
    clean = re.sub(r'\s{3,}', '\n\n', clean)
    clean = clean.strip()

    if not clean:
        raise ValueError('النص فارغ بعد التنظيف')

    # استخدام صوت بديل إذا لم يكن الصوت الأساسي متاحاً
    voice = 'ar-SA'
    try:
        communicate = edge_tts.Communicate(clean, voice)
    except Exception as e:
        # محاولة صوت بديل
        voice = 'ar-EG-AminaNeural'
        try:
            communicate = edge_tts.Communicate(clean, voice)
        except Exception as e2:
            # محاولة صوت آخر
            voice = 'ar-SA-HamadNeural'
            communicate = edge_tts.Communicate(clean, voice)

    # ✅ تفعيل WordBoundary events
    # بعض الأصوات تحتاج إلى تفعيل صريح لهذه الميزة
    try:
        communicate = edge_tts.Communicate(clean, voice, rate='+0%')
    except:
        pass
    
    audio_bytes: bytearray  = bytearray()
    word_timings: list[dict] = []

    # ✅ تتبع إزاحة الأحرف في النص المنظف
    current_char_offset = 0

    # ✅ stream() يُعطي كلا audio و WordBoundary
    try:
        async for chunk in communicate.stream():
            ctype = chunk.get('type', '')
            if ctype == 'audio':
                audio_bytes.extend(chunk.get('data', b''))
            elif ctype == 'WordBoundary':
                word   = chunk.get('text', '').strip()
                offset = chunk.get('offset',   0)   # 100-nanoseconds
                dur    = chunk.get('duration', 0)   # 100-nanoseconds
                if word:
                    # حساب إزاحة الأحرف في النص المنظف
                    char_offset = clean.find(word, current_char_offset)
                    if char_offset == -1:
                        # إذا لم يُعثر على الكلمة، استخدم الإزاحة الحالية
                        char_offset = current_char_offset
                    else:
                        current_char_offset = char_offset + len(word)

                    word_timings.append({
                        'word':  word,
                        'start': round(offset          / 10_000_000, 3),
                        'end':   round((offset + dur)  / 10_000_000, 3),
                        'char_offset': char_offset,
                        'char_length': len(word),
                    })
    except Exception as e:
        logger.warning(f'[utils] stream() failed: {e}, trying save() fallback')
        # fallback: save() مباشرة (بدون WordBoundary)
        try:
            communicate2 = edge_tts.Communicate(clean, voice)
            await communicate2.save(full_path)
            logger.info(f'[utils] Audio saved via save() fallback: {file_path}')
            return None  # لا يوجد timing في save()
        except Exception as e2:
            raise ValueError(f'فشل في توليد الصوت (stream و save فشلا): {str(e2)}')

    # ── حفظ MP3 ────────────────────────────────────────────
    if audio_bytes:
        with open(full_path, 'wb') as f:
            f.write(audio_bytes)
        logger.info(f'[utils] Audio saved: {file_path} ({len(audio_bytes)} bytes)')
    else:
        # fallback: save() مباشرة (بدون WordBoundary)
        logger.warning('[utils] stream() returned no audio bytes, using save() fallback')
        try:
            communicate2 = edge_tts.Communicate(clean, voice)
            await communicate2.save(full_path)
            logger.info(f'[utils] Audio saved via save() fallback: {file_path}')
        except Exception as e:
            raise ValueError(f'فشل في توليد الصوت (save fallback): {str(e)}')

    # ── حفظ timing JSON ────────────────────────────────────
    timing_rel = None
    if word_timings:
        timing_rel  = file_path + '.json'
        timing_full = full_path + '.json'
        with open(timing_full, 'w', encoding='utf-8') as f:
            _json.dump(word_timings, f, ensure_ascii=False, indent=None)
        logger.info(f'[utils] Timing saved: {timing_rel} ({len(word_timings)} words)')
    else:
        logger.warning('[utils] No WordBoundary events — word highlighting unavailable')

    return timing_rel


# ══════════════════════════════════════════════════════════════
# Azure Speech Service - توليد الصوت مع WordBoundary
# ══════════════════════════════════════════════════════════════
def generate_audio_azure(text: str, file_path: str) -> str | None:
    """
    توليد الصوت باستخدام Azure Speech Service مع استخراج توقيتات الكلمات

    Args:
        text: النص المراد تحويله إلى صوت
        file_path: مسار ملف الصوت النسبي (داخل MEDIA_ROOT)

    Returns:
        مسار ملف التوقيت JSON النسبي، أو None إذا فشل
    """
    azure_key = getattr(settings, 'AZURE_SPEECH_KEY', '')
    azure_region = getattr(settings, 'AZURE_SPEECH_REGION', 'eastus')

    if not azure_key:
        logger.warning('[utils] Azure Speech Key not configured, falling back to edge_tts')
        return None

    try:
        # تنظيف النص
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'[*#_~`\\]', '', clean)
        clean = re.sub(r'-{2,}', ' ', clean)
        clean = re.sub(r'\s{3,}', '\n\n', clean)
        clean = clean.strip()

        if not clean:
            raise ValueError('النص فارغ بعد التنظيف')

        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # إعداد Azure Speech
        speech_config = speechsdk.SpeechConfig(
            subscription=azure_key,
            region=azure_region
        )
        speech_config.speech_synthesis_voice_name = "ar-SA-HamedNeural"
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
        )

        audio_config = speechsdk.audio.AudioOutputConfig(filename=full_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        words_timestamps = []
        current_char_offset = 0

        # معالج WordBoundary
        def word_boundary_handler(evt):
            nonlocal current_char_offset
            start_time = evt.audio_offset / 10000000.0  # تحويل من 100-nanosecond إلى ثوانٍ
            duration = evt.duration.total_seconds()

            # حساب إزاحة الأحرف في النص المنظف
            word = evt.text.strip()
            if word:
                char_offset = clean.find(word, current_char_offset)
                if char_offset == -1:
                    char_offset = current_char_offset
                else:
                    current_char_offset = char_offset + len(word)

                words_timestamps.append({
                    "word": word,
                    "start": round(start_time, 3),
                    "end": round(start_time + duration, 3),
                    "char_offset": char_offset,
                    "char_length": len(word)
                })

        synthesizer.synthesis_word_boundary.connect(word_boundary_handler)

        # توليد الصوت
        result = synthesizer.speak_text_async(clean).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # حفظ ملف التوقيتات JSON
            if words_timestamps:
                timing_rel = file_path + '.json'
                timing_full = full_path + '.json'
                with open(timing_full, 'w', encoding='utf-8') as f:
                    _json.dump(words_timestamps, f, ensure_ascii=False, indent=None)
                logger.info(f'[utils] Azure Speech: Audio saved: {file_path} ({len(words_timestamps)} words)')
                logger.info(f'[utils] Azure Speech: Timing saved: {timing_rel}')
                return timing_rel
            else:
                logger.warning('[utils] Azure Speech: No word boundaries captured')
                return None
        else:
            logger.error(f'[utils] Azure Speech Failed: {result.reason}')
            return None

    except Exception as e:
        logger.error(f'[utils] Azure Speech Error: {str(e)}')
        return None


# ══════════════════════════════════════════════════════════════
# خرائط التعليم ADHD
# ══════════════════════════════════════════════════════════════
_SUBJECT_CONFIG: dict = {
    'رياضيات': {
        'style':   'قصصي حسابي — اربط كل رقم بقصة من حياة الطالب',
        'voice':   'حيّ ومتحمس، كأنك تحل لغزاً ممتعاً',
        'example': 'تخيّل معي أنك في السوق وعندك عشر تفاحات...',
    },
    'علوم': {
        'style':   'استكشافي تساؤلي — ابدأ بسؤال ثم اكشف الإجابة',
        'voice':   'مثير للفضول، كأنك تكشف سراً خفياً',
        'example': 'هل تساءلت يوماً لماذا تسقط الأشياء للأسفل؟',
    },
    'فيزياء': {
        'style':   'تطبيقي محسوس — اربط القوانين بظواهر يومية',
        'voice':   'منطقي ومبسّط',
        'example': 'عندما تركل كرةً بقوة تذهب بعيداً — قانون نيوتن!',
    },
    'كيمياء': {
        'style':   'تشبيهي حياتي — اجعل التفاعلات قصة بين مكوّنات المطبخ',
        'voice':   'بسيط ومدهش',
        'example': 'الملح في طعامك ناتج تفاعل بين معدنَين!',
    },
    'أحياء': {
        'style':   'جسدي استكشافي — ابدأ من جسم الطالب',
        'voice':   'دافئ ومتعاطف',
        'example': 'اليوم سنكتشف كيف يتنفس قلبك...',
    },
    'لغة عربية': {
        'style':   'سردي جمالي — اجعل الكلمات تحكي حكاية',
        'voice':   'أدبي وجميل',
        'example': 'كانت الكلمات تتجوّل في الجملة تبحث عن مكانها...',
    },
    'لغة إنجليزية': {
        'style':   'حواري تدريجي — كلمات جديدة داخل جمل بسيطة',
        'voice':   'مشجّع ومبسّط',
        'example': 'كلمة واحدة جديدة كل يوم — وهكذا نبني لغة كاملة!',
    },
    'تاريخ': {
        'style':   'قصصي زمني — احكِ التاريخ كرواية',
        'voice':   'راوٍ متحمس',
        'example': 'في ذلك اليوم البعيد قرر القائد أن يغيّر مجرى التاريخ...',
    },
    'جغرافيا': {
        'style':   'رحلة استكشافية — اصطحب الطالب على الخريطة',
        'voice':   'مغامر ومستكشف',
        'example': 'تعال نركب طائرة خيالية ونحلّق فوق هذا البلد!',
    },
    'تربية إسلامية': {
        'style':   'قيمي قصصي — ابدأ بقصة نبوية',
        'voice':   'هادئ تأملي',
        'example': 'حدث يوماً أن جاء رجل للنبي ﷺ...',
    },
    'دراسات اجتماعية': {
        'style':   'مجتمعي قصصي — اربط بقصص من الحياة',
        'voice':   'اجتماعي وودود',
        'example': 'تخيّل أنك في مدرستك — كيف يتعاون الجميع؟',
    },
    'تربية وطنية': {
        'style':   'قصصي انتمائي',
        'voice':   'فخور ومحفّز',
        'example': 'هل تعلم أن في بلدنا أناساً عظماء غيّروا العالم؟',
    },
    'حاسوب': {
        'style':   'منطقي خطوي',
        'voice':   'منطقي ومرح',
        'example': 'الحاسوب مثلك — يتبع التعليمات خطوة بخطوة!',
    },
}

_GRADE_AGE_MAP: dict = {
    'الثاني': 7, 'الثالث': 8, 'الرابع': 9, 'الخامس': 10,
    'السادس': 11, 'السابع': 12, 'الثامن': 13, 'التاسع': 14,
    'العاشر': 15,
    'الحادي عشر العلمي': 16, 'الحادي عشر الأدبي': 16,
    'الحادي عشر الصناعي': 16, 'الحادي عشر التجاري': 16,
    'الحادي عشر الزراعي': 16,
}

_GRADE_PROFILES = [
    (range(7,  10), {
        'stage': 'ابتدائية دنيا', 'attention_span': '5-10 دقائق',
        'needs': 'قصص قصيرة جداً، كلمات بسيطة، تكرار لطيف',
        'language': 'جمل 5-7 كلمات. مفردات من المنزل والمدرسة.',
        'avoid': 'المصطلحات الأكاديمية، الجمل المركبة، التجريد',
        'hook': 'ابدأ بحيوان أو طفل يشبه الطالب أو لعبة مألوفة',
    }),
    (range(10, 13), {
        'stage': 'ابتدائية عليا', 'attention_span': '10-15 دقيقة',
        'needs': 'قصص فيها تشويق، أمثلة من الألعاب والأصدقاء',
        'language': 'جمل 7-10 كلمات. مصطلح واحد مع شرحه.',
        'avoid': 'الشرح النظري المجرد، التفاصيل الزائدة',
        'hook': 'ابدأ بتحدٍّ أو سؤال مفاجئ',
    }),
    (range(12, 16), {
        'stage': 'إعدادية', 'attention_span': '15-20 دقيقة',
        'needs': 'ربط بالواقع والمستقبل، أمثلة من التقنية',
        'language': 'جمل طبيعية. 2-3 مصطلحات مشروحة.',
        'avoid': 'التبسيط المُهين، الأمثلة الطفولية',
        'hook': 'حقيقة مدهشة أو سؤال ماذا لو',
    }),
    (range(15, 19), {
        'stage': 'ثانوية', 'attention_span': '20-25 دقيقة',
        'needs': 'التفكير النقدي، ربط بالمستقبل المهني',
        'language': 'جمل كاملة، مصطلحات أكاديمية مشروحة.',
        'avoid': 'التبسيط المفرط',
        'hook': 'إشكالية حقيقية أو سؤال فلسفي',
    }),
]


def _get_grade_profile(age: int) -> dict:
    for rng, profile in _GRADE_PROFILES:
        if age in rng:
            return profile
    return _GRADE_PROFILES[2][1]


def _get_subject_cfg(subject_name: str) -> dict:
    if not subject_name:
        return {}
    for key, cfg in _SUBJECT_CONFIG.items():
        if key in subject_name or subject_name in key:
            return cfg
    sn = subject_name.lower()
    KEYWORDS = {
        'رياض': 'رياضيات', 'علوم': 'علوم', 'فيزياء': 'فيزياء',
        'كيمياء': 'كيمياء', 'أحياء': 'أحياء', 'احياء': 'أحياء',
        'عربي': 'لغة عربية', 'إنجليز': 'لغة إنجليزية', 'انجليز': 'لغة إنجليزية',
        'تاريخ': 'تاريخ', 'جغرافيا': 'جغرافيا',
        'إسلامية': 'تربية إسلامية', 'اسلامية': 'تربية إسلامية',
        'اجتماع': 'دراسات اجتماعية', 'وطني': 'تربية وطنية',
        'حاسوب': 'حاسوب', 'computer': 'حاسوب', 'تكنولوجيا': 'حاسوب',
    }
    for kw, cfg_key in KEYWORDS.items():
        if kw in sn or kw in subject_name:
            return _SUBJECT_CONFIG.get(cfg_key, {})
    return {}


# ══════════════════════════════════════════════════════════════
# System Prompt ADHD
# ══════════════════════════════════════════════════════════════
def _build_adhd_instruction(
    subject_name: str, lesson_title: str, class_name: str,
    student_age: int, grade_name: str, para_count: int,
) -> str:
    p   = _get_grade_profile(student_age)
    cfg = _get_subject_cfg(subject_name)

    subject_label = subject_name or 'المادة الدراسية'
    grade_label   = ('الصف ' + grade_name) if grade_name else 'المرحلة المتوسطة'
    age_display   = str(student_age) + ' سنة'

    adhd_lines = [
        f'الطالب: ADHD، عمره {age_display}، {p.get("stage", "")}.',
        f'• مدة تركيزه: {p.get("attention_span", "")} — بعدها ينفصل.',
        f'• يحتاج: {p.get("needs", "")}',
        f'• لغته: {p.get("language", "")}',
        f'• تجنّب: {p.get("avoid", "")}',
        f'• السنارة: {p.get("hook", "")}',
        '',
        'حقائق ADHD:',
        '① القصص تُتذكر 3× أكثر من الحقائق.',
        '② الجملة التي تبدأ بـ "أنت" تُعيد الانتباه.',
        '③ كل 70 كلمة يحتاجون hook.',
        '④ الجملة 7-10 كلمات تُقلل التفكك المعرفي.',
        '⑤ ربط المعلومة بحياة الطالب يُعزز التذكر 5×.',
    ]

    if cfg:
        method_lines = [
            '',
            f'استراتيجية مادة {subject_label}:',
            f'• أسلوب: {cfg.get("style", "")}',
            f'• نبرة: {cfg.get("voice", "")}',
            f'• نموذج: {cfg.get("example", "")}',
        ]
    else:
        method_lines = [f'\nأسلوب مناسب لـ {subject_label}. ابدأ بمثال حياتي.']

    para_roles = [
        'الشرارة — سؤال أو موقف مشوّق',
        'القصة — الفكرة الأولى بمثال حياتي',
        'التعمق — الفكرة الثانية مع رابط للحياة',
        'الاكتشاف — سر أو حقيقة مفاجئة',
        'التطبيق — كيف يستخدم الطالب هذا؟',
        'الإلهام — جملة ختامية مُلهِمة',
    ]
    hook_ex = p.get('hook', 'ابدأ بسؤال مثير')

    json_parts = ['  {"type": "hook", "paragraph": "جملة افتتاحية مشوّقة"}']
    for i in range(para_count):
        role = para_roles[i] if i < len(para_roles) else 'فقرة محتوى'
        json_parts.append(f'  {{"type": "content", "paragraph": "فقرة {i+1} — {role}"}}')
    json_parts.append('  {"type": "summary", "paragraph": "ملخص مُلهِم"}')
    json_example = '[\n' + ',\n'.join(json_parts) + '\n]'

    lines = [
        'SYSTEM: أنت ADHD-Specialist Educational Narrator.',
        f'السياق: {subject_label} | {grade_label} | {age_display} | {lesson_title or "غير محدد"}\n',
        *adhd_lines,
        *method_lines,
        '',
        '═══ قواعد الفقرات — مُلزِمة ═══',
        '【1】كل فقرة content: 60-90 كلمة.',
        '【2】الجملة الأولى: 7 كلمات أو أقل.',
        '【3】كل فقرة تبدأ بـ: سؤال / مفاجأة / "أنت" / تشجيع.',
        '【4】بعد كل فكرة: جملة تشجيع قصيرة.',
        '【5】ممنوع: * # _ ~ ` | "في هذا الدرس" | "وخلاصة القول"',
        '【6】لغة مناسبة للـ TTS: فواصل ونقاط طبيعية.',
        '',
        '═══ الأسلوب القصصي والتنقيط — مُلزِم ═══',
        '【1】استخدم أسلوب قصصي مبسط يناسب عمر الطالب ومادة الدراسة.',
        '【2】استخدم النقاط (•) لعرض الأفكار الرئيسية داخل الفقرات.',
        '【3】ميّز الكلمات المهمة والمفاهيم الأساسية بـ **bold** (مثال: **الضوء**، **الطاقة**).',
        '【4】اجعل القصة مشوّقة ومترابطة مع حياة الطالب.',
        '【5】استخدم لغة بسيطة ومباشرة مناسبة للصف المستهدف.',
        '',
        '═══ الحركات المهمة للنطق الصحيح — مُلزِم ═══',
        '【1】ضع الحركات المهمة على الكلمات التي قد يخطئ في نطقها نظام TTS.',
        '【2】استخدم الحركات العربية: اً (ألف مقصورة)، اً (تنوين)، اً (همزة)، اً (شدة).',
        '【3】أضف الحركات على الكلمات المهمة والمفاهيم الأساسية.',
        '【4】مثال: "الضوءُ" بدلاً من "الضوء"، "الطاقةُ" بدلاً من "الطاقة".',
        '【5】لا تُكثر من الحركات، فقط الكلمات المهمة التي قد يخطئ في نطقها.',
        '',
        f'═══ بنية الدرس: hook + {para_count} فقرات + summary ═══',
        f'❶ hook: {hook_ex}',
        *[f'❷ content {i+1}: {para_roles[i]}' for i in range(para_count)],
        '❸ summary: ملخص مُلهِم.',
        '',
        '═══ صيغة الإخراج الوحيدة ═══',
        'JSON array فقط، لا نص قبله أو بعده:',
        json_example,
        '',
        '═══ التوجيه النهائي ═══',
        'إذا فقد الطالب تركيزه في السطر الثالث — فشلنا.',
        'إذا وصل للنهاية ويريد المزيد — نجحنا.',
        'حوّل نص الدرس التالي إلى تجربة تعليمية لا تُنسى:',
    ]
    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════
# الدالة الرئيسية
# ══════════════════════════════════════════════════════════════
def process_lesson_with_ai(
    original_text: str,
    agent_data,
    user_id: int,
    teacher_prompts: list | None = None,
    subject_name: str = '',
    lesson_title:  str = '',
    class_name:    str = '',
    teacher=None,
) -> tuple[str, str | None, list]:
    """
    Returns:
        (simplified_text, audio_rel_path, [])
        audio_rel_path + '.json' = ملف timing للتظليل
    """
    print('\n--- 🏁 بدء المعالجة الشاملة للدرس ---')
    timestamp = int(time.time())

# ── مفتاح API ────────────────────────────────────────────
    teacher_obj = teacher or getattr(agent_data, '_teacher_hint', None)
    api_key, model = _resolve_api_key(agent_data, teacher_obj)
    print(f'[utils] API key={api_key[:8]}..., model={model!r}')

    # ── تحديد العمر والصف ─────────────────────────────────────
    grade_name  = ''
    student_age = 12
    for text in [class_name or '', lesson_title or '', subject_name or '']:
        for grade, age in _GRADE_AGE_MAP.items():
            if grade in text:
                grade_name  = grade
                student_age = age
                break
        if grade_name:
            break

    # ── عدد الفقرات ───────────────────────────────────────────
    word_count = len(original_text.split())
    if   word_count < 100: para_count = 3
    elif word_count < 250: para_count = 4
    elif word_count < 500: para_count = 5
    else:                  para_count = 6

    instruction = _build_adhd_instruction(
        subject_name, lesson_title, class_name,
        student_age, grade_name, para_count,
    )
    prompt_content = f'--- نص الدرس ---\n{original_text}'

    # 1️⃣ تبسيط النص
    print('1️⃣ جاري تبسيط النص...')
    simplified_text = ''

    try:
        full_res = _call_gemini(api_key, model, instruction, prompt_content)
        if not full_res:
            raise ValueError('Gemini لم يُعِد نصاً')

        paragraphs_list = []
        
        # ✅ استخراج مصفوفة الـ JSON مباشرة بشكل منظم
        json_match = re.search(r'\[\s*\{.*\}\s*\]', full_res, re.DOTALL)
        if json_match:
            try:
                # التنظيف المسبق واستخراج الـ JSON
                sanitized_str = _sanitize_json_str(json_match.group())
                parsed = _json.loads(sanitized_str)
                
                # فرز وتجميع الأقسام حسب النوع (hook -> content -> summary)
                hooks     = [x for x in parsed if isinstance(x, dict) and x.get('type') == 'hook']
                contents  = [x for x in parsed if isinstance(x, dict) and x.get('type') == 'content']
                summaries = [x for x in parsed if isinstance(x, dict) and x.get('type') == 'summary']
                
                ordered = hooks + contents + summaries if (hooks or summaries) else parsed

                for item in ordered:
                    if isinstance(item, dict):
                        p_text = item.get('paragraph', '').strip()
                        if p_text:
                            # تحويل **bold** إلى <strong> وإزالة الرموز غير المرغوبة
                            p_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', p_text)
                            p_text = re.sub(r'[#_~`]', '', p_text).strip()
                            paragraphs_list.append(p_text)
            except Exception as parse_err:
                logger.warning(f'[utils] Failed to parse JSON array: {parse_err}')

        if paragraphs_list:
            simplified_text = '\n\n'.join(paragraphs_list)
        else:
            # ✅ Fallback: في حال فشل استخراج الـ JSON، يتم تنظيف النص العادي القادم من Gemini
            raw = re.sub(r'\[\s*\{.*\}\s*\]', '', full_res, flags=re.DOTALL)
            raw = re.sub(r'[*#_~`]', '', raw)
            raw = re.sub(r'^\s*[-–—]\s+', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'^\s*\d+\.\s+', '', raw, flags=re.MULTILINE)
            simplified_text = re.sub(r'\n{3,}', '\n\n', raw).strip()

        print('✅ تم تجهيز النص بنجاح.')

    except Exception as e:
        print(f'❌ فشل تبسيط النص: {e}')
        logger.error(f'[utils] Simplification failed: {e}')
        simplified_text = re.sub(r'[*#_~`-]', '', original_text)

    # 2️⃣ توليد الصوت + timing
    audio_rel_path = f'lessons/audio/audio_{user_id}_{timestamp}.mp3'
    print('2️⃣ جاري توليد الملف الصوتي...')
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError('closed')
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        timing_path = loop.run_until_complete(
            generate_audio_async(simplified_text, audio_rel_path)
        )
        print(f'✅ تم توليد الصوت: {audio_rel_path}')
        if timing_path:
            print(f'✅ ملف التظليل: {timing_path}')
        else:
            print('⚠️ ملف التظليل غير متاح (WordBoundary لم تُستقبل)')
    except Exception as e:
        print(f'⚠️ فشل توليد الصوت: {e}')
        logger.error(f'[utils] Audio generation failed: {e}')
        audio_rel_path = None

    print('--- 🏁 انتهت العملية بنجاح ---')
    return simplified_text, audio_rel_path, []