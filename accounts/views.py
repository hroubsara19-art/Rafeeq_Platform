"""
accounts/views.py — محسّن بالأمان
"""
import logging, os, re, traceback
import random
import string
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from .main_forms import RegistrationForm
from .info_forms import StudentProfileForm, TeacherProfileForm, ParentProfileForm
from learning.models import Student, Teacher, Parent
from django.contrib.auth import logout as auth_logout
import edge_tts
import asyncio
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import io

logger = logging.getLogger(__name__)

_ALLOWED_AVATAR_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
_MAX_AVATAR_SIZE    = 2 * 1024 * 1024
_VALID_ROLES = {'Student', 'Teacher', 'Parent', 'SysAdmin', 'Admin'}


def _sanitize_text(value, max_len=300):
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(value))
    return value.strip()[:max_len]


def _safe_next_url(request):
    """منع Open Redirect."""
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url, allowed_hosts={request.get_host()}
    ) and 'logout' not in next_url.lower():
        return next_url
    return None


def redirect_by_role(user):
    """إعادة التوجيه حسب الدور مع التحقق من اكتمال الملف الشخصي."""
    if user.is_superuser or user.is_staff:
        return redirect('learning:teacher_dashboard')

    role = getattr(user, 'userrole', None)

    if role == 'SysAdmin':
        return redirect('admin_portal:dashboard')
    if role == 'Admin':
        # الأدمن التقني يرى واجهة الطالب
        return redirect('student:student_home')
    if role not in _VALID_ROLES:
        return redirect('accounts:login')

    try:
        if role == 'Student':
            s = Student.objects.only('age', 'classid').get(userid=user)
            if not s.classid or not s.age or s.age < 7:
                return redirect('accounts:complete_profile')
            return redirect('student:student_home')

        elif role == 'Teacher':
            t = Teacher.objects.only('specialization').get(userid=user)
            if not t.specialization or t.specialization == 'General':
                return redirect('accounts:complete_profile')
            return redirect('learning:teacher_dashboard')

        elif role == 'Parent':
            p = Parent.objects.only('childid').get(userid=user)
            if not p.childid:
                return redirect('accounts:complete_profile')
            return redirect('parent:parent_portal')

    except (Student.DoesNotExist, Teacher.DoesNotExist, Parent.DoesNotExist):
        return redirect('accounts:complete_profile')

    return redirect('accounts:login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == 'POST':
        username = _sanitize_text(request.POST.get('username', ''), 50).lower()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'هذا الحساب معطّل. تواصل مع الإدارة.')
                return render(request, 'accounts/login.html')

            login(request, user)
            request.session.set_expiry(10800 if request.POST.get('remember_me') else 0)
            request.session.cycle_key()

            next_url = _safe_next_url(request)
            if next_url and 'complete_profile' not in next_url:
                return redirect(next_url)

            return redirect_by_role(user)

        messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    request.session.cycle_key()
    auth_logout(request)
    messages.info(request, 'تم تسجيل الخروج بنجاح.')
    return redirect('accounts:login')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data.get('userrole')
            if role not in _VALID_ROLES:
                form.add_error('userrole', 'دور غير مسموح به.')
            else:
                try:
                    # ✅ حفظ المستخدم أولاً بشكل مستقل — لا يتأثر بفشل الملف الشخصي
                    user = form.save(commit=False)
                    user.is_active = False  # غير مفعل حتى يتم التحقق من الإيميل
                    user.save()
                    
                    # إنشاء رمز التحقق من 8 خانات
                    verification_code = ''.join(random.choices(string.digits, k=8))
                    user.email_verification_code = verification_code
                    user.email_verification_sent_at = timezone.now()
                    user.save()
                    
                    # إرسال الإيميل
                    try:
                        subject = 'رمز التحقق من EduPal'
                        message = f'''
مرحباً {user.fullname}،

شكراً لتسجيلك في منصة EduPal.

رمز التحقق الخاص بك هو: {verification_code}

يرجى إدخال هذا الرمز في صفحة التحقق لتفعيل حسابك.

رمز التحقق صالح لمدة 30 دقيقة.

تحياتنا،
فريق EduPal
'''
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        logger.error(f"Email sending error: {e}")
                        form.add_error(None, 'حدث خطأ أثناء إرسال الإيميل. يرجى المحاولة مرة أخرى.')
                        user.delete()
                        return render(request, 'accounts/signup.html', {'form': form})
                    
                    # ✅ إنشاء الملف الشخصي منفصلاً — فشله لا يحذف المستخدم
                    try:
                        if role == 'Student':
                            Student.objects.get_or_create(userid=user, defaults={'age': 1})
                        elif role == 'Teacher':
                            Teacher.objects.get_or_create(userid=user, defaults={'specialization': 'General'})
                        elif role == 'Parent':
                            Parent.objects.get_or_create(userid=user, defaults={'childid': None})
                    except Exception as e:
                        logger.error(f"Profile creation error for user {user.pk}: {e}")

                    # حفظ البريد الإلكتروني في session للتحقق
                    request.session['verification_email'] = user.email
                    
                    messages.success(request, 'تم إنشاء الحساب! يرجى التحقق من بريدك الإلكتروني لإدخال رمز التحقق.')
                    return redirect('accounts:verify_email')
                    
                except Exception as e:
                    logger.error(f"Signup user creation error: {e}\n{traceback.format_exc()}")
                    form.add_error(None, 'حدث خطأ أثناء إنشاء الحساب.')
                    return render(request, 'accounts/signup.html', {'form': form})

    else:
        form = RegistrationForm()

    return render(request, 'accounts/signup.html', {'form': form})


def verify_email_view(request):
    """صفحة التحقق من الرمز المرسل للإيميل"""
    email = request.session.get('verification_email')
    if not email:
        messages.warning(request, 'يرجى تسجيل حساب أولاً.')
        return redirect('accounts:signup')
    
    if request.method == 'POST':
        code = request.POST.get('verification_code', '').strip()
        
        if not code:
            messages.error(request, 'يرجى إدخال رمز التحقق.')
            return render(request, 'accounts/verify_email.html', {'email': email})
        
        # البحث عن المستخدم بالبريد الإلكتروني
        from learning.models import User
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'المستخدم غير موجود.')
            return redirect('accounts:signup')
        
        # التحقق من الرمز
        if user.email_verification_code != code:
            messages.error(request, 'رمز التحقق غير صحيح.')
            return render(request, 'accounts/verify_email.html', {'email': email})
        
        # التحقق من انتهاء صلاحية الرمز (30 دقيقة)
        if user.email_verification_sent_at:
            time_diff = timezone.now() - user.email_verification_sent_at
            if time_diff > timedelta(minutes=30):
                messages.error(request, 'رمز التحقق منتهي الصلاحية. يرجى طلب رمز جديد.')
                return render(request, 'accounts/verify_email.html', {'email': email})
        
        # تفعيل الحساب
        user.is_active = True
        user.is_email_verified = True
        user.email_verification_code = None
        user.email_verification_sent_at = None
        user.save()
        
        # تسجيل الدخول
        login(request, user)
        rotate_token(request)
        
        # مسح البريد من session
        del request.session['verification_email']
        
        messages.success(request, 'تم تفعيل حسابك بنجاح!')
        return redirect('accounts:complete_profile')
    
    return render(request, 'accounts/verify_email.html', {'email': email})


@login_required
def complete_profile(request):
    user = request.user
    role = getattr(user, 'userrole', None)

    if user.is_staff or user.is_superuser:
        return redirect('learning:teacher_dashboard')
    if role not in _VALID_ROLES:
        return redirect('accounts:login')

    form_map = {
        'Student': (Student, StudentProfileForm),
        'Teacher': (Teacher, TeacherProfileForm),
        'Parent':  (Parent,  ParentProfileForm),
    }

    if role not in form_map:
        return redirect('accounts:login')

    model_class, form_class = form_map[role]
    instance, _ = model_class.objects.get_or_create(userid=user)

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    profile = form.save(commit=False)
                    if role == 'Parent':
                        profile.childid = form.cleaned_data.get('student_identity')
                    profile.save()
                    if hasattr(form, 'save_m2m'):
                        form.save_m2m()
                messages.success(request, 'تم تحديث بياناتك بنجاح!')
                return redirect_by_role(user)
            except Exception as e:
                logger.error(f"complete_profile error: {e}")
                messages.error(request, f'خطأ في الحفظ: {str(e)}')
    else:
        form = form_class(instance=instance)

    return render(request, 'accounts/complete_profile.html', {'form': form, 'role': role})


@login_required
def home_view(request):
    return redirect_by_role(request.user)


@csrf_exempt
def generate_voice(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        text = data.get('text', '')
        
        async def get_audio():
            communicate = edge_tts.Communicate(
                text, 
                "ar-SA-ZariyahNeural", 
                rate="+15%", 
                pitch="+30Hz"
            )
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            return audio_data.getvalue()
        
        audio_bytes = asyncio.run(get_audio())
        
        return HttpResponse(audio_bytes, content_type='audio/mpeg')