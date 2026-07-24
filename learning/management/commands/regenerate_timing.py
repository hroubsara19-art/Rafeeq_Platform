from django.core.management.base import BaseCommand
from learning.models import Lessoncontent
from learning.utils import generate_audio_async
import asyncio
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'إعادة توليد ملفات التوقيت للدروس القديمة التي لديها صوت بدون توقيت'

    def add_arguments(self, parser):
        parser.add_argument(
            '--lesson-id',
            type=int,
            help='معرف الدرس المحدد لإعادة توليد التوقيت له',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='إعادة توليد التوقيت لجميع الدروس القديمة',
        )

    def handle(self, *args, **options):
        lesson_id = options.get('lesson_id')
        regenerate_all = options.get('all')

        if lesson_id:
            self.regenerate_lesson_timing(lesson_id)
        elif regenerate_all:
            self.regenerate_all_timings()
        else:
            self.stdout.write(self.style.WARNING('يرجى تحديد --lesson-id أو --all'))

    def regenerate_lesson_timing(self, lesson_id):
        try:
            lesson = Lessoncontent.objects.get(pk=lesson_id)
        except Lessoncontent.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'الدرس {lesson_id} غير موجود'))
            return

        # التحقق من أن الدرس لديه نص
        lesson_text = lesson.ai_generatedtext or lesson.originaltext or ''
        if not lesson_text:
            self.stdout.write(self.style.WARNING(f'الدرس {lesson_id} ليس لديه نص'))
            return

        # التحقق من وجود ملف التوقيت بالفعل (ملف JSON بجانب MP3)
        if lesson.ai_audiopath:
            audio_path = os.path.join(settings.MEDIA_ROOT, str(lesson.ai_audiopath).lstrip('/'))
            timing_path = audio_path + '.json'
            if os.path.exists(timing_path):
                self.stdout.write(self.style.WARNING(f'الدرس {lesson_id} لديه ملف توقيت بالفعل: {timing_path}'))
                response = input('هل تريد الاستمرار في إعادة التوليد؟ (y/n): ')
                if response.lower() != 'y':
                    return

        self.stdout.write(f'جاري إعادة توليد الصوت والتوقيت للدرس: {lesson.lessontitle}')

        try:
            # تنظيف النص
            import re
            clean_text = re.sub(r'<[^>]+>', ' ', lesson_text)
            clean_text = re.sub(r'[*#_~`\\]', '', clean_text)
            clean_text = re.sub(r'-{2,}', ' ', clean_text)
            clean_text = re.sub(r'\s{3,}', '\n\n', clean_text)
            clean_text = clean_text.strip()

            if not clean_text:
                self.stdout.write(self.style.ERROR('النص فارغ بعد التنظيف'))
                return

            # توليد الصوت والتوقيت معاً
            import time as _time_m
            _ts = int(_time_m.time())
            _rel = f'lessons/audio/audio_{lesson.teacherid_id}_{_ts}.mp3'

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            timing_rel = loop.run_until_complete(generate_audio_async(clean_text, _rel))
            loop.close()

            if timing_rel:
                # تحديث مسار الصوت فقط في قاعدة البيانات (حيث يتم حفظ التوقيت تلقائياً كملف JSON مجاور)
                lesson.ai_audiopath = _rel
                lesson.save(update_fields=['ai_audiopath'])
                
                self.stdout.write(self.style.SUCCESS('تم توليد الصوت والتوقيت بنجاح'))
                self.stdout.write(f'الصوت: {_rel}')
                self.stdout.write(f'التوقيت: {timing_rel}')
            else:
                self.stdout.write(self.style.WARNING('فشل في توليد التوقيت (قد لا يدعم الصوت WordBoundary)'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'حدث خطأ: {str(e)}'))
            logger.error(f'Error regenerating timing for lesson {lesson_id}: {e}')

    def regenerate_all_timings(self):
        # البحث عن الدروس التي لديها صوت بدون ملف توقيت JSON
        lessons = Lessoncontent.objects.filter(
            ai_audiopath__isnull=False
        ).exclude(
            ai_audiopath=''
        )

        # تصفية الدروس التي ليس لديها ملف JSON بجانب ملف الصوت
        lessons_without_timing = []
        for lesson in lessons:
            if lesson.ai_audiopath:
                audio_path = os.path.join(settings.MEDIA_ROOT, str(lesson.ai_audiopath).lstrip('/'))
                timing_path = audio_path + '.json'
                if not os.path.exists(timing_path):
                    lessons_without_timing.append(lesson)

        lessons = lessons_without_timing

        count = len(lessons)
        if count == 0:
            self.stdout.write(self.style.SUCCESS('جميع الدروس لديها ملفات توقيت'))
            return

        self.stdout.write(f'وجدت {count} درس بدون ملف توقيت')
        response = input('هل تريد الاستمرار؟ (y/n): ')
        if response.lower() != 'y':
            return

        for i, lesson in enumerate(lessons, 1):
            self.stdout.write(f'\n[{i}/{count}] معالجة الدرس: {lesson.lessontitle}')
            self.regenerate_lesson_timing(lesson.pk)

        self.stdout.write(self.style.SUCCESS('\nتم الانتهاء من معالجة جميع الدروس'))