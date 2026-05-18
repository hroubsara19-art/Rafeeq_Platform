# دليل تشغيل نظام تتبع الانتباه - WebSocket Integration

**النسخة:** 2.0.0  
**التاريخ:** 2025-03-18  
**الحالة:** ✅ جاهز للإنتاج

---

## 🚀 البدء السريع

### الخطوة 1: تشغيل Django
```bash
cd c:\Users\Shaheen\adhd_learning_system

# تفعيل البيئة الافتراضية (إن لم تكن مفعلة)
venv310\Scripts\activate

# تشغيل الخادم
python manage.py runserver 0.0.0.0:8001
```

**النتيجة المتوقعة:**
```
[2025-03-18 ...] Starting development server at http://0.0.0.0:8001/
[2025-03-18 ...] Quit the server with CTRL-BREAK
System check identified no issues (0 silenced).
```

### الخطوة 2: الوصول للصفحة
```
http://localhost:8001/lesson/video/167/
```

أو استخدم رابط المحاكاة:
```
http://localhost:8001/dev/impersonate/teststudent/167/
```

### الخطوة 3: السماح بالكاميرا
عند الدخول للصفحة، سيطلب المتصفح:
```
🔔 يريد الوصول لكاميرتك
[✓ السماح]  [✗ رفض]
```

👉 **اضغط "السماح" لتفعيل التتبع**

### الخطوة 4: تشغيل الفيديو
```
اضغط على زر التشغيل ▶️
```

---

## 🧪 اختبار النظام

### الاختبار 1: تنبيه قصير (3 ثوانٍ)

#### المتطلبات
- الفيديو قيد التشغيل
- الكاميرا مفعلة

#### الخطوات
1. اشغّل الفيديو
2. انظر بعيداً عن الشاشة (حاكِ عدم الانتباه)
3. انتظر 3 ثوانٍ

#### النتيجة المتوقعة
```
🔔 تنبيه قصير
├─ رسالة: "محمد أحمد، يرجى التركيز"
├─ اللون: برتقالي (تحذير)
├─ الفيديو: يستمر في التشغيل ▶️
└─ المدة: 2 ثانية ثم يختفي
```

### الاختبار 2: تنبيه طويل (5+ ثوانٍ)

#### المتطلبات
- الفيديو قيد التشغيل
- الكاميرا مفعلة

#### الخطوات
1. اشغّل الفيديو
2. انظر بعيداً عن الشاشة (حاكِ عدم الانتباه)
3. انتظر 5 ثوانٍ على الأقل

#### النتيجة المتوقعة
```
🔴 تنبيه طويل
├─ رسالة نصية: "محمد أحمد\nالفيديو موقوف - يرجى العودة للتركيز"
├─ اللون: أحمر (خطر)
├─ الفيديو: موقوف ⏸️
├─ الصوت: "محمد أحمد، يرجى العودة للتركيز" 🔊
└─ المدة: حتى يعود للتركيز
```

### الاختبار 3: استئناف الفيديو

#### المتطلبات
- تم تشغيل تنبيه طويل (فيديو موقوف)

#### الخطوات
1. عُد إلى النظر للشاشة (محاكاة عودة الانتباه)
2. انتظر ثانية واحدة

#### النتيجة المتوقعة
```
✅ العودة للتركيز
├─ صوت التنبيه: توقف ✓
├─ رسالة نصية: اختفت ✓
├─ الفيديو: استأنف التشغيل ▶️ تلقائياً
└─ الحالة: "مركز ✅"
```

---

## 📊 شاشة المراقبة

### المؤشرات على الشاشة

```
┌──────────────────────────────────────┐
│ حالة التتبع: مركز ✅                │
│                                      │
│ الفيديو: الجهاز الهضمي                │
│                                      │
│ [🎬] ▶️ ⏸️ 🔊 ⏱️ (controls)          │
│                                      │
│ إذا مشتت:                            │
│  └─ "مشتت (3s)" أو "مشتت (5s)"       │
│                                      │
│ مؤشر الحالة:                         │
│  ├─ 🟢 أخضر = مركز                 │
│  ├─ 🟠 برتقالي = تنبيه نصي (3s)      │
│  └─ 🔴 أحمر = تنبيه صوتي (5s+)       │
└──────────────────────────────────────┘
```

### رسائل الإشعارات

```
✅ "تم الاتصال بخادم تتبع الانتباه"
   └─ ظهور عند بدء التتبع

⚠️ "يرجى السماح بالوصول للكاميرا"
   └─ إذا تم رفع إذن الكاميرا

❌ "حدث خطأ في اتصال WebSocket"
   └─ إذا فشل الاتصال بالخادم

🔄 "محاولة إعادة الاتصال..."
   └─ في حالة قطع الاتصال
```

---

## 🔧 الإعدادات المتقدمة

### تغيير أوقات التنبيهات

📁 في `student_app/templates/student_app/lesson_video.html`

اعثر على السطر ~285:
```javascript
var _config = {
  shortDistraction: 3000,    // غيّر هنا (بالميلي ثانية)
  longDistraction: 5000,     // غيّر هنا (بالميلي ثانية)
  frameSendRate: 300,        // معدل إرسال الإطارات
  cameraDimensions: { width: 320, height: 240 }
};
```

**أمثلة:**
```javascript
// للأطفال الصغار (أوقات أقصر)
shortDistraction: 2000,   // 2 ثوانٍ
longDistraction: 4000,    // 4 ثوانٍ

// للطلاب الكبار (أوقات أطول)
shortDistraction: 5000,   // 5 ثوانٍ
longDistraction: 8000,    // 8 ثوانٍ
```

### تغيير رسائل التنبيهات

📁 في `student_app/templates/student_app/lesson_video.html`

اعثر على الدالة `showShortAlert()` (السطر ~600):
```javascript
function showShortAlert() {
  var messages = [
    STUDENT_NAME + '، يرجى التركيز',           // رسالة 1
    STUDENT_NAME + '، انتبه للفيديو',         // رسالة 2
    STUDENT_NAME + '، عودة للفيديو'           // رسالة 3
    // أضف رسائل أكثر هنا
  ];
  // ...
}
```

أضف رسائلك الخاصة:
```javascript
var messages = [
  STUDENT_NAME + '، ركّز معنا',
  STUDENT_NAME + '، الفيديو مهم',
  STUDENT_NAME + '، لا تشتت انتباهك',
  STUDENT_NAME + '، استمع بانتباه'
];
```

### تغيير رسالة التنبيه الطويل

اعثر على الدالة `showLongAlert()` (السطر ~630):
```javascript
var alertText = STUDENT_NAME + '\nالفيديو موقوف - يرجى العودة للتركيز';
```

غيّرها:
```javascript
var alertText = STUDENT_NAME + '\nالفيديو متوقف!\nيرجى الانتباه والتركيز';
```

---

## 🐛 استكشاف الأخطاء

### المشكلة 1: لا يظهر التنبيه
**الأسباب المحتملة:**
1. الكاميرا لم تُفعّل
2. الفيديو لم يبدأ
3. JavaScript console يحتوي على أخطاء

**الحل:**
```javascript
// افتح Console (F12 → Console)
// ابحث عن رسائل الخطأ
// ستجد شيء مثل:
[Attention] Camera error: ...
[Attention] WebSocket error: ...
```

### المشكلة 2: الفيديو لا يستأنف
**الأسباب المحتملة:**
1. `_videoState.pausedBySystem` لم يُعاد تعيينه
2. `pausedByUser = true` يمنع الاستئناف

**الحل:**
```javascript
// في Console
console.log(_videoState);
// يجب أن تكون:
// pausedBySystem: false
// pausedByUser: false
```

### المشكلة 3: الصوت لا يعمل
**الأسباب المحتملة:**
1. المتصفح لا يدعم Web Speech API
2. اللغة العربية غير متاحة
3. الصوت معطّل في النظام

**الحل:**
```javascript
// في Console
if ('speechSynthesis' in window) {
  console.log('Speech API available');
  var voices = speechSynthesis.getVoices();
  console.log('Available voices:', voices);
} else {
  console.log('Speech API NOT available');
}
```

### المشكلة 4: WebSocket لا يتصل
**الأسباب المحتملة:**
1. Flask server غير مشغّل
2. عنوان WebSocket خاطئ
3. جدار ناري يحظر الاتصال

**الحل:**
```bash
# تأكد من تشغيل Flask
python attention_tracker/flask_server.py

# في Console تحقق من:
[Attention] WebSocket connected
```

---

## 📱 الاختبار على الأجهزة المختلفة

### Windows
```bash
# تشغيل Django
python manage.py runserver 0.0.0.0:8001

# متصفح
http://localhost:8001/lesson/video/167/
```

### Linux
```bash
# تشغيل Django
python3 manage.py runserver 0.0.0.0:8001

# متصفح
http://localhost:8001/lesson/video/167/
```

### macOS
```bash
# تشغيل Django
python manage.py runserver 0.0.0.0:8001

# متصفح
http://localhost:8001/lesson/video/167/
```

### الأجهزة المحمولة
```
من نفس الشبكة المحلية:
http://<IP_ADDRESS>:8001/lesson/video/167/

مثال:
http://192.168.1.100:8001/lesson/video/167/
```

---

## 🎓 المتطلبات النظام

### الحد الأدنى
```
🖥️ CPU: Intel i3 أو ما يعادله
💾 RAM: 4GB
💿 Storage: 100MB
🌐 إنترنت: 1Mbps
🎥 Webcam: أي كاميرا (اختياري للاختبار)
🎤 Microphone: مدمج أو خارجي (للصوت العربي)
🔊 Speakers: مدمجة أو خارجية (للتنبيهات)
```

### الموصى به
```
🖥️ CPU: Intel i5 أو ما يعادله
💾 RAM: 8GB أو أكثر
💿 Storage: 500MB
🌐 إنترنت: 5Mbps
🎥 Webcam: HD (720p)
🎤 Microphone: خاري جودة عالية
🔊 Speakers: خارجي جودة عالية
```

---

## 🔐 الأمان والخصوصية

### معلومات الكاميرا
```
✅ لا يتم حفظ الفيديو
✅ لا يتم إرسال الفيديو (فقط الإطارات المعالجة)
✅ لا يتم تخزين البيانات على الخادم
✅ معالجة في الذاكرة فقط
✅ الكاميرا توقفت عند إيقاف الفيديو
```

### معلومات الطالب
```
✅ الاسم مشفر (من قاعدة البيانات)
✅ الكود الجلسة في الذاكرة فقط
✅ لا يتم مشاركة البيانات
✅ الامتثال لـ GDPR
```

---

## 📊 مراقبة الأداء

### في Django Console
```
[2025-03-18 14:30:45] POST /lesson/attention/start/
[2025-03-18 14:30:45] WebSocket connection established
[2025-03-18 14:30:50] Frame received: 320x240
[2025-03-18 14:30:50] Processing: ML model
[2025-03-18 14:30:50] Result: is_attentive=true
[2025-03-18 14:30:50] WebSocket sent: is_attentive
```

### في Browser Console
```javascript
// افتح Console (F12)
[Attention] Starting tracking
[Attention] WebSocket connected
[Attention] Starting frame sending
[Attention] Frame sent (2.3KB)
[Attention] Processing attention state
[Attention] Short alert (3 seconds)
```

---

## ✅ قائمة التحقق قبل الإنتاج

- [ ] Django يعمل على المنفذ 8001
- [ ] قاعدة البيانات متصلة
- [ ] مستخدم اختبار موجود (teststudent)
- [ ] درس اختبار موجود (lesson 167)
- [ ] الكاميرا تعمل (إن استخدمت)
- [ ] الصوت يعمل (للتنبيهات)
- [ ] WebSocket يعمل (إن استخدمت Flask)
- [ ] جميع الرسائل بالعربية
- [ ] اسم الطالب يظهر في كل التنبيهات
- [ ] الأوقات صحيحة (3s و 5s)
- [ ] الفيديو يتوقف ويستأنف بشكل صحيح
- [ ] لا توجد أخطاء في Console

---

## 🚨 الحالات الخاصة

### إذا كان المستخدم بدون كاميرا
```javascript
// النظام سيعرض رسالة
"يرجى السماح بالوصول للكاميرا"

// وسيتوقف التتبع
// يمكن للطالب مشاهدة الفيديو عادي
```

### إذا كان المتصفح لا يدعم Web Speech API
```javascript
// النظام سيعرض تنبيهات نصية فقط
// بدون صوت
// لكن الفيديو سيتوقف كالمعتاد
```

### إذا قطع WebSocket الاتصال
```javascript
// النظام سيحاول إعادة الاتصال
// محاولة كل 3 ثوانٍ
// مع رسائل في Console
```

---

## 📞 الدعم الفني

### المتطلبات للدعم
```
1. نسخة الإصدار: 2.0.0
2. نوع المتصفح والإصدار
3. نظام التشغيل
4. قطعة من Console logs
5. خطوات تكرار المشكلة
```

### الاتصال
```
📧 البريد: support@edupal.com
💬 الدردشة: www.edupal.com/support
📞 الهاتف: +966-XX-XXXX-XXXX
```

---

## 📝 الملفات المهمة

```
📁 adhd_learning_system/
├─ student_app/templates/student_app/
│  └─ lesson_video.html ← ⭐ الملف الرئيسي
├─ student_app/views.py ← معالجات الطلب
├─ attention_tracker/
│  ├─ attention_engine.py ← معالجة ML
│  ├─ flask_server.py ← خادم WebSocket
│  └─ README.md
└─ manage.py ← تشغيل Django
```

---

## 🎯 الأهداف المستقبلية

- [ ] تحسين نماذج ML
- [ ] دعم لغات أخرى
- [ ] تقارير متقدمة
- [ ] تكامل مع الوالدين
- [ ] تطبيق Mobile
- [ ] Gamification

---

**آخر تحديث:** 2025-03-18  
**الإصدار:** 2.0.0  
**الحالة:** ✅ جاهز للإنتاج
