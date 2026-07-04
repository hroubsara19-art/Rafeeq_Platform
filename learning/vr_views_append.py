

# ══════════════════════════════════════════════════════════════
# VR Setup Views
# ══════════════════════════════════════════════════════════════

@login_required
@teacher_required
def vr_lesson_setup(request):
    """
    صفحة إعداد تجربة الواقع الافتراضي للدرس
    - تختار المعلم الصف والمادة والدرس
    - يضيف رابط موقع الواقع الافتراضي
    - يتم حفظ البيانات للطالب
    """
    from .forms import VRLessonSetupForm
    
    teacher = request.teacher
    
    if request.method == 'POST':
        form = VRLessonSetupForm(request.POST, teacher=teacher)
        if form.is_valid():
            try:
                classroom = form.cleaned_data['classroom']
                subject = form.cleaned_data['subject']
                lesson = form.cleaned_data['lesson']
                vr_url = form.cleaned_data['vr_url']
                
                # التحقق من أن الدرس يخص المعلم
                if lesson.teacherid != teacher:
                    messages.error(request, 'هذا الدرس لا يخصك.')
                    return render(request, 'learning/vr_lesson_setup.html', {'form': form})
                
                # إنشاء أو تحديث سجل الواقع الافتراضي
                vr_lesson, created = VRLesson.objects.update_or_create(
                    lesson=lesson,
                    defaults={
                        'teacher': teacher,
                        'subject': subject,
                        'classroom': classroom,
                        'vr_url': vr_url,
                        'is_published': True,
                    }
                )
                
                message_type = 'إنشاء' if created else 'تحديث'
                messages.success(
                    request,
                    f'تم {message_type} تجربة الواقع الافتراضي بنجاح للدرس "{lesson.lessontitle}"'
                )
                
                # إعادة التوجيه للصفحة السابقة أو لوحة التحكم
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url, allowed_hosts={request.get_host()}
                ):
                    return redirect(next_url)
                return redirect('learning:teacher_dashboard')
                
            except Exception as e:
                logger.exception(f"Error setting up VR lesson: {e}")
                messages.error(request, 'حدث خطأ أثناء حفظ تجربة الواقع الافتراضي.')
                return render(request, 'learning/vr_lesson_setup.html', {'form': form})
    else:
        form = VRLessonSetupForm(teacher=teacher)
    
    # بيانات إضافية لتمرير رابط منصة التصميم
    design_platform_url = 'https://ai.studio/apps/84df996b-346c-484f-a8e5-23b34c70a90d'
    
    return render(request, 'learning/vr_lesson_setup.html', {
        'form': form,
        'design_platform_url': design_platform_url,
        'teacher': teacher,
    })


@login_required
@teacher_required
def vr_lesson_edit(request, vr_id):
    """تعديل تجربة واقع افتراضي موجودة"""
    from .forms import VRLessonSetupForm
    from django.shortcuts import get_object_or_404
    
    teacher = request.teacher
    vr_lesson = get_object_or_404(VRLesson, vr_id=vr_id, teacher=teacher)
    
    if request.method == 'POST':
        form = VRLessonSetupForm(request.POST, teacher=teacher)
        if form.is_valid():
            try:
                vr_lesson.classroom = form.cleaned_data['classroom']
                vr_lesson.subject = form.cleaned_data['subject']
                vr_lesson.lesson = form.cleaned_data['lesson']
                vr_lesson.vr_url = form.cleaned_data['vr_url']
                vr_lesson.save()
                
                messages.success(request, f'تم تحديث تجربة الواقع الافتراضي بنجاح.')
                return redirect('learning:teacher_dashboard')
                
            except Exception as e:
                logger.exception(f"Error updating VR lesson: {e}")
                messages.error(request, 'حدث خطأ أثناء تحديث الواقع الافتراضي.')
    else:
        # ملء النموذج بالبيانات الحالية
        initial_data = {
            'classroom': vr_lesson.classroom,
            'subject': vr_lesson.subject,
            'lesson': vr_lesson.lesson,
            'vr_url': vr_lesson.vr_url,
        }
        form = VRLessonSetupForm(initial=initial_data, teacher=teacher)
    
    design_platform_url = vr_lesson.design_platform_url
    
    return render(request, 'learning/vr_lesson_setup.html', {
        'form': form,
        'vr_lesson': vr_lesson,
        'design_platform_url': design_platform_url,
        'teacher': teacher,
        'is_edit': True,
    })


@login_required
@require_POST
def vr_lesson_delete(request, vr_id):
    """حذف تجربة واقع افتراضي"""
    from django.shortcuts import get_object_or_404
    
    teacher = request.teacher if hasattr(request, 'teacher') else Teacher.objects.filter(userid=request.user).first()
    
    if not teacher:
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        vr_lesson = get_object_or_404(VRLesson, vr_id=vr_id, teacher=teacher)
        lesson_title = vr_lesson.lesson.lessontitle
        vr_lesson.delete()
        
        messages.success(request, f'تم حذف تجربة الواقع الافتراضي للدرس "{lesson_title}" بنجاح.')
        return redirect('learning:teacher_dashboard')
        
    except Exception as e:
        logger.exception(f"Error deleting VR lesson: {e}")
        messages.error(request, 'حدث خطأ أثناء حذف الواقع الافتراضي.')
        return redirect('learning:teacher_dashboard')


# ══════════════════════════════════════════════════════════════
# API Endpoints for Dynamic Form Updates
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def get_subjects_for_class(request):
    """API: احصل على المواد حسب الصف والمعلم"""
    classroom_id = request.POST.get('classroom_id')
    
    if not classroom_id:
        return JsonResponse({'success': False, 'error': 'معرّف الصف مفقود'}, status=400)
    
    teacher = request.teacher if hasattr(request, 'teacher') else Teacher.objects.filter(userid=request.user).first()
    
    if not teacher:
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        subjects = Subject.objects.filter(
            teacherid=teacher,
            classid_id=classroom_id
        ).values('id', 'subjectname')
        
        return JsonResponse({
            'success': True,
            'subjects': list(subjects)
        })
    except Exception as e:
        logger.exception(f"Error getting subjects: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def get_lessons_for_subject(request):
    """API: احصل على الدروس حسب المادة والمعلم"""
    subject_id = request.POST.get('subject_id')
    
    if not subject_id:
        return JsonResponse({'success': False, 'error': 'معرّف المادة مفقود'}, status=400)
    
    teacher = request.teacher if hasattr(request, 'teacher') else Teacher.objects.filter(userid=request.user).first()
    
    if not teacher:
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        lessons = Lessoncontent.objects.filter(
            teacherid=teacher,
            subjectid_id=subject_id
        ).values('id', 'lessontitle', 'status')
        
        return JsonResponse({
            'success': True,
            'lessons': list(lessons)
        })
    except Exception as e:
        logger.exception(f"Error getting lessons: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
