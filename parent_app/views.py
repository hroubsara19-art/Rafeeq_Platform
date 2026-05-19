"""
parent_app/views.py — مُحدَّث
"""
import json
import logging
import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from learning.models import Parent, Performancereport, Student
from accounts.models import Notification

logger = logging.getLogger(__name__)

_ALLOWED_AVATAR_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
_MAX_AVATAR_SIZE    = 2 * 1024 * 1024

_MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpg',
    b'\x89PNG':      'png',
    b'GIF8':         'gif',
    b'RIFF':         'webp',
}


def _verify_image(file_obj) -> bool:
    header = file_obj.read(12)
    file_obj.seek(0)
    for magic in _MAGIC_BYTES:
        if header.startswith(magic):
            return True
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return True
    return False


def _parent_required(view_func):
    from functools import wraps
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        role = getattr(request.user, 'userrole', None)
        if role not in ('Parent',) and not request.user.is_staff:
            messages.error(request, 'هذه الصفحة لأولياء الأمور فقط.')
            return redirect('accounts:login')
        parent = Parent.objects.filter(
            userid=request.user
        ).select_related('childid__userid').first()
        if not parent and not request.user.is_staff:
            messages.warning(request, 'يرجى إكمال بياناتك أولاً.')
            return redirect('accounts:complete_profile')
        request.parent_obj = parent
        return view_func(request, *args, **kwargs)
    return wrapper


@_parent_required
def parent_portal(request):
    parent = request.parent_obj
    reports, child, avg_score = [], None, 0

    if parent and parent.childid:
        child   = parent.childid
        reports = list(
            Performancereport.objects
            .filter(studentid=child)
            .select_related('lessonid__subjectid', 'lessonid__teacherid__userid')
            .order_by('-reportdate')
        )
        scores    = [r.testscore for r in reports if r.testscore is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # ── الإشعارات الجديدة لولي الأمر ────────────────────────────
    unread_notifications = []
    all_notifications    = []
    if child:
        all_notifications = list(
            Notification.objects
            .filter(
                recipient  = request.user,
                notif_type__in = [
                    'parent_lesson', 'parent_test', 'parent_result',
                    'parent_attention', 'parent_grade', 'schedule_update',
                ],
            )
            .order_by('-created_at')[:30]
        )
        unread_notifications = [n for n in all_notifications if not n.is_read]
        # ✅ عدم تعليم الإشعارات كمقروءة تلقائياً - يترك ذلك للمستخدم

    # ── تجميع تقارير المواد ──────────────────────────────────────
    subject_reports = []
    if reports:
        from collections import defaultdict
        from learning.models import Lessoncontent
        subj_map = defaultdict(list)
        for r in reports:
            if r.lessonid and r.lessonid.subjectid:
                subj_map[r.lessonid.subjectid.subjectname].append(r)
        for subj_name, reps in subj_map.items():
            scores_list = [r.testscore for r in reps if r.testscore is not None]
            avg_g  = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
            # حساب نسبة الإنجاز بناءً على عدد الدروس المكتملة فعلياً مقارنة بالعدد الكلي للدروس في المادة
            subject_id = reps[0].lessonid.subjectid.subjectid if reps[0].lessonid and reps[0].lessonid.subjectid else None
            total_lessons = Lessoncontent.objects.filter(subjectid=subject_id).count() if subject_id else 0
            completed_lessons = len(set(r.lessonid.lessonid for r in reps if r.lessonid))
            completion = round((completed_lessons / total_lessons * 100), 1) if total_lessons > 0 else 0
            completion = min(100, completion)
            subject_reports.append({
                'subject_name': subj_name,
                'completion':   completion,
                'grade':        f'{avg_g}%',
            })

    # ملاحظات المعلمين (إشعارات parent_grade + parent_attention + teachercomments من التقارير)
    teacher_notes = []
    # أولاً: من الإشعارات
    for n in all_notifications:
        if n.notif_type in ('parent_attention', 'parent_grade'):
            teacher_name = getattr(n, 'sender_name', None) or 'النظام'
            if hasattr(n, 'sender') and n.sender:
                teacher_name = n.sender.fullname if hasattr(n.sender, 'fullname') else str(n.sender)
            teacher_notes.append({
                'teacher_name': teacher_name,
                'date':         n.created_at.strftime('%Y-%m-%d'),
                'text':         n.body,
            })
    # ثانياً: من تعليقات المعلمين في التقارير (إذا وجدت)
    if reports:
        for r in reports[:5]:
            if r.teachercomments and r.teachercomments.strip():
                teacher_name = 'المعلم'
                if r.lessonid and r.lessonid.teacherid and r.lessonid.teacherid.userid:
                    teacher_name = r.lessonid.teacherid.userid.fullname
                teacher_notes.append({
                    'teacher_name': teacher_name,
                    'date':         r.reportdate.strftime('%Y-%m-%d') if r.reportdate else '',
                    'text':         r.teachercomments,
                })
    # ترتيب الملاحظات حسب التاريخ (الأحدث أولاً)
    teacher_notes.sort(key=lambda x: x['date'], reverse=True)
    teacher_notes = teacher_notes[:5]

    # ── بيانات الرسم البياني للتركيز (بيانات حقيقية) ───────────────
    chart_data = {
        'labels': [],
        'attention_scores': [],
        'test_scores': [],
    }
    if reports:
        # تجميع البيانات حسب الأسبوع
        from collections import defaultdict
        from datetime import datetime, timedelta
        weekly_data = defaultdict(lambda: {'attention': [], 'tests': []})
        
        for r in reports:
            if r.reportdate:
                week_start = r.reportdate - timedelta(days=r.reportdate.weekday())
                week_key = week_start.strftime('%Y-%m-%d')
                if r.avgattentionscore is not None:
                    weekly_data[week_key]['attention'].append(r.avgattentionscore)
                if r.testscore is not None:
                    weekly_data[week_key]['tests'].append(r.testscore)
        
        # ترتيب الأسابيع وحساب المتوسطات
        sorted_weeks = sorted(weekly_data.keys())[:4]  # آخر 4 أسابيع
        for week in sorted_weeks:
            week_label = datetime.strptime(week, '%Y-%m-%d').strftime('%d/%m')
            chart_data['labels'].append(week_label)
            att_scores = weekly_data[week]['attention']
            test_scores = weekly_data[week]['tests']
            avg_att = round(sum(att_scores) / len(att_scores), 1) if att_scores else 0
            avg_test = round(sum(test_scores) / len(test_scores), 1) if test_scores else 0
            chart_data['attention_scores'].append(avg_att)
            chart_data['test_scores'].append(avg_test)
    
    # إذا لم يكن هناك بيانات، استخدم بيانات فارغة
    if not chart_data['labels']:
        chart_data = {
            'labels': ['الأسبوع 1', 'الأسبوع 2', 'الأسبوع 3', 'الأسبوع 4'],
            'attention_scores': [0, 0, 0, 0],
            'test_scores': [0, 0, 0, 0],
        }

    return render(request, 'parent_app/parent_portal.html', {
        'parent':                parent,
        'child':                 child,
        'reports':               reports[:10],
        'avg_score':             avg_score,
        'subject_reports':       subject_reports,
        'all_notifications':     all_notifications,
        'unread_notifications':  unread_notifications,
        'unread_count':          len(unread_notifications),
        'teacher_notes':         teacher_notes,
        'chart_data':            json.dumps(chart_data, ensure_ascii=False),
    })


@login_required
def parent_profile(request):
    parent = Parent.objects.filter(
        userid=request.user
    ).select_related('childid__userid', 'userid').first()
    child  = parent.childid if parent else None

    if request.method == 'POST':
        bio    = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', request.POST.get('bio', '')).strip()[:300]
        avatar = request.FILES.get('avatar')
        remove = request.POST.get('remove_avatar') == '1'
        errors = []

        if remove and not avatar:
            if request.user.avatar:
                request.user.avatar.delete(save=False)
            request.user.avatar = None
            request.user.bio = bio
            request.user.save(update_fields=['avatar', 'bio'])
            messages.success(request, 'تمت إزالة الصورة وحفظ الملف الشخصي.')
            return redirect('parent:profile')

        if avatar:
            ext = os.path.splitext(avatar.name)[1].lower()
            if ext not in _ALLOWED_AVATAR_EXT:
                errors.append('صيغة الصورة غير مدعومة.')
            elif avatar.size > _MAX_AVATAR_SIZE:
                errors.append('حجم الصورة يتجاوز 2MB.')
            elif not _verify_image(avatar):
                errors.append('الملف المرفوع ليس صورة صحيحة.')
            else:
                fname = f'avatars/parent_{request.user.pk}{ext}'
                fpath = os.path.join(settings.MEDIA_ROOT, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, 'wb') as dest:
                    for chunk in avatar.chunks():
                        dest.write(chunk)
                request.user.avatar = fname

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            request.user.bio = bio
            update_fields = ['bio']
            if avatar and not errors:
                update_fields.append('avatar')
            request.user.save(update_fields=update_fields)
            messages.success(request, 'تم حفظ الملف الشخصي.')
        return redirect('parent:profile')

    return render(request, 'parent_app/profile.html', {
        'parent': parent,
        'child':  child,
    })