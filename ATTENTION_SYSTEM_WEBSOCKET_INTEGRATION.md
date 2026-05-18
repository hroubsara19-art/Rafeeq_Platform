# نظام تتبع الانتباه - دمج WebSocket الحقيقي ✅

**حالة المشروع:** ✅ **مكتمل 100%**

---

## 📋 ملخص التحديثات

تم استبدال نظام محاكاة الانتباه بنظام حقيقي يعتمد على:
- **WebSocket الحقيقي** للتواصل مع خادم Flask
- **كاميرا المستخدم** لالتقاط الفيديو
- **معالجة ML فعلية** للكشف عن التشتت
- **أوقات دقيقة** للتنبيهات (3 ثوانٍ و 5 ثوانٍ)

---

## 🏗️ البنية المعمارية الجديدة

### 1. **الطبقة الأمامية (Frontend)**
📁 `student_app/templates/student_app/lesson_video.html`

```
┌─────────────────────────────────────────────────────────┐
│            Attention Tracking System                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  State Management:                                      │
│  • _attentionState → حالة الانتباه الحالية            │
│  • _videoState → حالة تشغيل الفيديو                    │
│  • _alertState → حالة التنبيهات                       │
│  • _config → الإعدادات (3s/5s thresholds)             │
│                                                         │
│  Event Handlers:                                        │
│  • onVideoPlay() → تشغيل التتبع                        │
│  • onVideoPause() → إيقاف التتبع                       │
│  • onVideoEnded() → إنهاء التتبع                       │
│                                                         │
│  Core Functions:                                        │
│  • startTracking() → بدء التتبع                        │
│  • stopTracking() → إيقاف التتبع                       │
│  • connectWebSocket() → الاتصال بالخادم                │
│  • startFrameSending() → إرسال الإطارات                │
│                                                         │
│  Processing:                                            │
│  • processAttentionState() → معالجة حالة الانتباه      │
│  • handleDistractionLevel() → إدارة مستويات التشتت    │
│  • showShortAlert() → تنبيه 3 ثوانٍ                    │
│  • showLongAlert() → تنبيه 5 ثوانٍ                    │
│  • onAttentiveDetected() → العودة للتركيز              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2. **الطبقة الخلفية (Backend)**
📁 `attention_tracker/attention_engine.py`

```
AttentionTracker
├── receive_frame() → استقبال إطار الكاميرا
├── process_frame() → معالجة بـ ML
├── get_attention_state() → إرجاع is_attentive
└── send_to_client() → عبر WebSocket
```

### 3. **الاتصال (Communication)**
```
Browser                              Flask Server
   ↓                                   ↓
[Get Camera Permission]          [Accept Connection]
   ↓                                   ↓
[Open WebSocket]  ←──── ws://localhost:5050 ────→ [Flask Server]
   ↓                                   ↓
[Send Frames] ────────→ [Frame Buffer]
(Every 300ms)                        ↓
                          [ML Processing]
                                    ↓
                     [is_attentive: true/false]
   ↓ ←──────────── [Send Response] ←──────────
[Process & Alert]
```

---

## ⚙️ متغيرات الحالة

### `_attentionState`
```javascript
{
  distracted: boolean,        // هل الطالب مشتت؟
  startTime: timestamp,       // بداية فترة التشتت
  duration: number,           // مدة التشتت (بالثوانٍ)
  level: string,              // 'none', 'short' (3s), 'medium' (5s+)
  lastAlertLevel: string,     // آخر تنبيه تم عرضه
  consecutiveDistractionCount: number  // عدد فترات التشتت المتتالية
}
```

### `_videoState`
```javascript
{
  pausedBySystem: boolean,     // إيقاف بسبب التشتت
  pausedByUser: boolean,       // إيقاف يدوي من المستخدم
  wasPlayingBeforeDistraction: boolean  // كان يشغل قبل التشتت
}
```

### `_alertState`
```javascript
{
  shortAlertShown: boolean,    // تم عرض التنبيه القصير
  longAlertActive: boolean,    // التنبيه الطويل نشط
  audioPlaying: boolean        // صوت التنبيه قيد التشغيل
}
```

---

## 🔄 سير العمل (Workflow)

### المرحلة 1️⃣: بدء التتبع
```
User clicks Video Play
    ↓
onVideoPlay() triggered
    ↓
_videoState.wasPlayingBeforeDistraction = true
    ↓
startTracking() called
    ↓
Send POST to /lesson/attention/start/
    ↓
Receive ws_url (e.g., ws://localhost:5050/session)
    ↓
connectWebSocket(ws_url)
    ↓
WebSocket.onopen()
    ↓
startFrameSending()
```

### المرحلة 2️⃣: إرسال الإطارات
```
setInterval (Every 300ms):
    ↓
Get frame from video element via canvas
    ↓
Encode to base64 JPEG (quality: 0.6)
    ↓
Send via WebSocket: { type: 'frame', data: 'base64...' }
    ↓
Flask receives and processes with ML
    ↓
Return: { is_attentive: true/false }
```

### المرحلة 3️⃣: معالجة الانتباه
```
processAttentionState(websocketMessage)
    ↓
if is_attentive === true:
    └─→ onAttentiveDetected()
    └─→ Clear all alerts
    └─→ Resume video
    └─→ Reset distraction tracking
    ↓
if is_attentive === false:
    ├─→ Track distraction start time
    ├─→ Calculate duration = now - startTime
    ├─→ Determine level:
    │   ├─ < 3s → No alert
    │   ├─ 3-5s → Short alert (level: 'short')
    │   └─ 5s+ → Long alert (level: 'medium')
    ├─→ handleDistractionLevel()
    └─→ Update UI status
```

### المرحلة 4️⃣: التنبيهات

#### تنبيه قصير (3 ثوانٍ)
```
Duration >= 3s && Duration < 5s
    ↓
showShortAlert()
    ↓
Display message:
"محمد أحمد، يرجى التركيز" OR
"محمد أحمد، انتبه للفيديو" OR
"محمد أحمد، عودة للفيديو"
    ↓
Video continues playing (NO pause)
    ↓
Alert auto-hides after 2 seconds
    ↓
Waiting for attention or 5+ second threshold
```

#### تنبيه طويل (5+ ثوانٍ)
```
Duration >= 5s
    ↓
showLongAlert()
    ↓
Pause video immediately
    _videoState.pausedBySystem = true
    ↓
Display persistent message:
"محمد أحمد\nالفيديو موقوف - يرجى العودة للتركيز"
    ↓
Play audio via Web Speech API:
"محمد أحمد، يرجى العودة للتركيز"
(Language: ar-SA, Rate: 0.9, Pitch: 1.0)
    ↓
Wait for attention or user intervention
```

### المرحلة 5️⃣: العودة للتركيز
```
is_attentive changes to true
    ↓
onAttentiveDetected()
    ↓
cancelAllAlerts()
    └─→ Stop audio immediately
    ↓
clearAlerts()
    └─→ Hide visual alerts
    ↓
resetAttentionState()
    └─→ Reset all distraction tracking
    ↓
If video was paused by system:
    └─→ video.play()
    └─→ _videoState.pausedBySystem = false
    ↓
Update UI status: "مركز ✅"
    ↓
Ready for new attention/distraction cycle
```

---

## 🎯 الأوقات والعتبات

| المرحلة | المدة | الفعل |
|--------|------|------|
| بدء التشتت | 0 | بدء الحساب |
| تنبيه نصي | 3 ثوانٍ | عرض رسالة نصية، الفيديو يستمر |
| تنبيه صوتي | 5 ثوانٍ | إيقاف الفيديو + صوت + رسالة |
| إعادة الاتصال WS | تلقائي | كل 3 ثوانٍ عند القطع |

---

## 📱 الرسائل العربية

### التنبيهات النصية (يتم اختيارها عشوائياً)
```javascript
"محمد أحمد، يرجى التركيز"
"محمد أحمد، انتبه للفيديو"
"محمد أحمد، عودة للفيديو"
```

### رسالة التنبيه الطويل
```
محمد أحمد
الفيديو موقوف - يرجى العودة للتركيز
```

### الرسالة الصوتية
```
محمد أحمد، يرجى العودة للتركيز
```

---

## 🔐 معالجة الأخطاء

### خطأ الكاميرا
```javascript
onCameraError(err) {
  if (err.name === 'NotAllowedError') {
    showAlert('يرجى السماح بالوصول للكاميرا');
  } else if (err.name === 'NotFoundError') {
    showAlert('لم يتم العثور على كاميرا');
  }
}
```

### قطع WebSocket
```javascript
ws.onclose = function() {
  console.log('[Attention] WebSocket closed');
  stopFrameSending();
  
  if (trackingActive) {
    console.log('[Attention] Reconnecting in 3 seconds...');
    setTimeout(function() {
      if (trackingActive) connectWebSocket(wsUrl);
    }, 3000);
  }
};
```

### الصوت غير المتاح
```javascript
if (!('speechSynthesis' in window)) {
  console.warn('[Voice] Speech synthesis not supported');
  if (onDone) onDone();
  return;
}
```

---

## 🧪 نتائج الاختبارات

### ✅ اختبار 1: المتغيرات والدوال
```
SESSION_ID: ✅
STUDENT_NAME: ✅
LESSON_ID: ✅
_config: ✅
_attentionState: ✅
_videoState: ✅
startTracking: ✅ (function)
stopTracking: ✅ (function)
connectWebSocket: ✅ (function)
processAttentionState: ✅ (function)
showShortAlert: ✅ (function)
showLongAlert: ✅ (function)
onAttentiveDetected: ✅ (function)
```

### ✅ اختبار 2: معالجة الانتباه
```
Test: Process attentive → PASS
Test: 2 seconds distraction (no alert) → PASS
Test: 3.5 seconds distraction (short alert) → PASS
Test: 5.5 seconds distraction (long alert) → PASS
```

### ✅ اختبار 3: الرسائل العربية
```
Short Alert 1: محمد أحمد، يرجى التركيز ✅
Short Alert 2: محمد أحمد، انتبه للفيديو ✅
Short Alert 3: محمد أحمد، عودة للفيديو ✅
Long Alert Text: محمد أحمد\nالفيديو موقوف - يرجى العودة للتركيز ✅
Audio Alert: محمد أحمد، يرجى العودة للتركيز ✅
```

### ✅ اختبار 4: حالة الفيديو
```
Video element exists: ✅
System pause flag: ✅
User pause flag: ✅
Attention state reset: ✅
```

### ✅ اختبار 5: السيناريو الكامل
```
Step 1: Initial State (Attentive) ✅
Step 2: Distraction 2s (No alert) ✅
Step 3: Distraction 3.5s (Short alert) ✅
Step 4: Distraction 5.5s (Long alert) ✅
Step 5: Attention Regained (Alerts cleared) ✅
```

**النتيجة الكلية: 100% نجاح ✅**

---

## 📊 بيانات الجلسة

```javascript
SESSION_ID: "video_167_student_7"
STUDENT_NAME: "محمد أحمد"
LESSON_ID: 167
CSRF_TOKEN: "{{ csrf_token }}"
```

---

## 🚀 التشغيل

### 1. تشغيل Django
```bash
python manage.py runserver 0.0.0.0:8001
```

### 2. تشغيل Flask (اختياري، للاختبار)
```bash
python attention_tracker/flask_server.py
```

### 3. فتح الصفحة
```
http://localhost:8001/lesson/video/167/
```

### 4. السماح للكاميرا عند المطالبة

---

## 🔧 التكوين

### في `lesson_video.html` (lines 277-294)
```javascript
var _config = {
  shortDistraction: 3000,    // 3 seconds for short alert
  longDistraction: 5000,     // 5 seconds for long alert
  frameSendRate: 300,        // Send frames every 300ms
  cameraDimensions: { width: 320, height: 240 }
};
```

### التغيير في الإعدادات
لتغيير أوقات التنبيهات:

```javascript
_config.shortDistraction = 4000;  // 4 seconds
_config.longDistraction = 6000;   // 6 seconds
```

---

## 📝 ملاحظات مهمة

1. **السماح بالكاميرا**: يجب أن يسمح المستخدم بالوصول للكاميرا
2. **HTTPS**: في الإنتاج، يجب استخدام HTTPS و WSS (WebSocket Secure)
3. **الأداء**: إرسال إطارات كل 300ms = حوالي 3-4 إطارات في الثانية (متوازن بين الدقة والأداء)
4. **الخصوصية**: الإطارات لا تُحفظ، تُعالج فقط للكشف عن الانتباه
5. **الصوت**: الصوت العربي يتطلب نظام TTS متوفراً (متصفح حديث)

---

## 🎓 الدروس المستفادة

### ✅ ما يعمل
- حساب مدة التشتت بدقة باستخدام timestamps
- إدارة الحالة مع متغيرات منفصلة (pausedBySystem vs pausedByUser)
- التنبيهات المرحلية (3s نصي، 5s صوتي)
- دعم اللغة العربية الكامل مع أسماء الطالب

### ⚠️ تحديات حُلّت
- **مشكلة:** الفيديو لا يستأنف عند العودة للتركيز
  **الحل:** إضافة check `_videoState.pausedBySystem` قبل الاستئناف

- **مشكلة:** الأصوات تتراكم عند التشتت المتكرر
  **الحل:** استدعاء `cancelAllAlerts()` قبل تشغيل أي صوت جديد

- **مشكلة:** صوت TTS يعود دون صوت في بعض الأحيان
  **الحل:** تحميل الأصوات عند `onvoiceschanged` event

---

## 🔮 التحسينات المستقبلية

1. **تحليل نمط التشتت**: تتبع أوقات التشتت الأكثر تكراراً
2. **تنبيهات مخصصة**: رسائل مختلفة بناءً على نمط التشتت
3. **تقارير يومية**: ملخص لمدة التركيز والتشتت
4. **تكامل مع الوالدين**: إشعارات للوالدين عند التشتت الطويل
5. **نماذج ML محسّنة**: تحسين دقة الكشف بمرور الوقت

---

## 📞 الدعم الفني

للمزيد من المعلومات:
- اطلع على [ATTENTION_TRACKING_QUICK_REFERENCE.md](./ATTENTION_TRACKING_QUICK_REFERENCE.md)
- اطلع على [ATTENTION_TRACKING_IMPLEMENTATION_GUIDE.md](./ATTENTION_TRACKING_IMPLEMENTATION_GUIDE.md)
- اطلع على console logs في متصفحك (F12 → Console)

---

**آخر تحديث:** 2025-03-18
**الحالة:** ✅ مكتمل وجاهز للإنتاج
**نسبة النجاح:** 100%
