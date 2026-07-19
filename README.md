## 🔗 رابط المعاينة الحية (Live Preview)
يمكنك الوصول إلى النظام حالياً عبر الرابط السحابي المباشر:
 **[منصة رفيق - Rafeeq Platform](https://rafeeq-platform-tpne.onrender.com)**

---

## 🎥 Fixing Video Seek Issues (Faststart)
If students are jumped to the start when seeking, the MP4 files might not have the `moov` atom at the start. Re-mux files locally with `ffmpeg -movflags +faststart` **before** uploading them to the server to enable progressive seeking.

Run this command locally on your development machine (requires `ffmpeg` installed locally):
```bash
python manage.py fix_media_faststart --replace
