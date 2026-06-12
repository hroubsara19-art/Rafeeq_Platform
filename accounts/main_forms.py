from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from learning.models import User
import re

# ترجمة رسائل Django الافتراضية لكلمة المرور إلى العربية
_PASSWORD_ERRORS_AR = {
    'This password is too short. It must contain at least 8 characters.':
        'كلمة المرور قصيرة جداً. يجب أن تحتوي على 8 رموز على الأقل.',
    'This password is too common.':
        'كلمة المرور شائعة جداً. اختر كلمة مرور أصعب.',
    'This password is entirely numeric.':
        'لا يمكن أن تتكون كلمة المرور من أرقام فقط.',
    'The password is too similar to the username.':
        'كلمة المرور مشابهة جداً لاسم المستخدم.',
    'The password is too similar to the first name.':
        'كلمة المرور مشابهة جداً للاسم الأول.',
    'The password is too similar to the last name.':
        'كلمة المرور مشابهة جداً للاسم الأخير.',
    'The password is too similar to the email address.':
        'كلمة المرور مشابهة جداً للبريد الإلكتروني.',
    'The password is too similar to the email.':
        'كلمة المرور مشابهة جداً للبريد الإلكتروني.',
}

def _translate_password_errors(errors):
    """يُحوّل رسائل خطأ كلمة المرور الإنجليزية إلى العربية."""
    translated = []
    for msg in errors:
        translated.append(_PASSWORD_ERRORS_AR.get(msg, msg))
    return translated


class RegistrationForm(forms.ModelForm):
    # 1. تعريف الحقول مع العناوين العربية والـ Placeholders المناسبة
    username = forms.CharField(
        label="اسم المستخدم",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اختر اسم مستخدم فريد'
        })
    )

    fullname = forms.CharField(
        label="الاسم الكامل",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل اسمك الثلاثي'
        })
    )

    email = forms.EmailField(
        label="البريد الإلكتروني",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@gmail.com'
        })
    )

    identitynumber = forms.CharField(
        label="رقم الهوية",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '9 أرقام بدون مسافات',
            'inputmode': 'numeric',
            'pattern': '[0-9]{9}',
            'maxlength': '9',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 9)"
        })
    )

    userrole = forms.ChoiceField(
        label="نوع الحساب",
        choices=User.USER_ROLES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )

    password = forms.CharField(
        label="كلمة المرور",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '8 رموز تشمل حروفاً وأرقاماً',
            'autocomplete': 'new-password',
            'onkeyup': 'checkPasswordStrength(this.value)'
        }),
        help_text="يجب أن تكون كلمة المرور قوية ومعقدة."
    )

    confirm_password = forms.CharField(
        label="تأكيد كلمة المرور",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'أعد كتابة كلمة المرور للتحقق',
            'autocomplete': 'new-password'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'fullname', 'email', 'identitynumber', 'userrole', 'password']

    # --- التحققات الأمنية ---

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise ValidationError("اسم المستخدم مطلوب.")
        username = username.lower()
        if len(username) < 3:
            raise ValidationError("اسم المستخدم يجب أن يكون 3 أحرف على الأقل.")
        if User.objects.filter(username=username).exists():
            raise ValidationError("اسم المستخدم موجود مسبقاً. يرجى اختيار اسم آخر.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("البريد الإلكتروني مطلوب.")
        email = email.lower()
        
        # التحقق من التنسيق
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("تنسيق البريد الإلكتروني غير صحيح. مثال: user@example.com")
        
        # التحقق من الدومين (أكثر مرونة)
        domain = email.split('@')[1] if '@' in email else ''
        # التحقق من أن الدومين يحتوي على نقطة واحدة على الأقل وينتهي بـ TLD صالح
        if not domain or '.' not in domain:
            raise ValidationError("الدومين غير صالح. تأكد من صحة البريد الإلكتروني.")
        
        # التحقق من أن الدومين لا يبدأ أو ينتهي بـ نقطة أو شرطة
        if domain.startswith('.') or domain.startswith('-') or domain.endswith('.') or domain.endswith('-'):
            raise ValidationError("الدومين غير صالح. تأكد من صحة البريد الإلكتروني.")
        
        # التحقق من أن TLD (الجزء بعد آخر نقطة) يحتوي على حروف فقط و2+ حروف
        tld = domain.split('.')[-1]
        if not tld or not tld.isalpha() or len(tld) < 2:
            raise ValidationError("الدومين غير صالح. تأكد من صحة البريد الإلكتروني.")
        
        # التحقق من الجزء قبل النقطة (مثل example في example.com)
        # يجب أن يحتوي على حروف/أرقام/شرطات فقط ولا يكون فارغاً
        parts = domain.split('.')
        for part in parts[:-1]:  # جميع الأجزاء ما عدا TLD
            if not part:
                raise ValidationError("الدومين غير صالح. تأكد من صحة البريد الإلكتروني.")
            # التحقق من أن الجزء يحتوي على حروف/أرقام/شرطات فقط
            if not re.match(r'^[a-zA-Z0-9-]+$', part):
                raise ValidationError("الدومين غير صالح. تأكد من صحة البريد الإلكتروني.")
            # التحقق من أن الجزء لا يبدأ أو ينتهي بـ شرطة
            if part.startswith('-') or part.endswith('-'):
                raise ValidationError("الدومين غير صالح. تأكد من صحة البريد الإلكتروني.")
        
        # التحقق من التكرار
        if User.objects.filter(email=email).exists():
            raise ValidationError("البريد الإلكتروني مسجل مسبقاً. يرجى استخدام بريد آخر أو تسجيل الدخول.")
        
        return email

    def clean_identitynumber(self):
        identity = self.cleaned_data.get('identitynumber')
        if not identity:
            raise ValidationError("رقم الهوية مطلوب.")
        identity_str = str(identity)
        
        if not identity_str.isdigit():
            raise ValidationError("رقم الهوية يجب أن يتكون من أرقام فقط.")
        if len(identity_str) != 9:
            raise ValidationError("رقم الهوية يجب أن يكون مكوناً من 9 أرقام.")
        if identity_str == '0' * 9:
            raise ValidationError("رقم الهوية غير صالح. لا يمكن أن يتكون من أصفار فقط.")
        if User.objects.filter(identitynumber=int(identity_str)).exists():
            raise ValidationError("رقم الهوية مسجل مسبقاً. يرجى التأكد من الرقم أو التواصل مع الدعم.")
        
        return int(identity_str)

    def clean_fullname(self):
        fullname = self.cleaned_data.get('fullname')
        if not fullname or len(fullname.strip()) < 3:
            raise ValidationError("الاسم الكامل مطلوب ويجب أن يكون 3 أحرف على الأقل.")
        return fullname.strip()

    def clean_userrole(self):
        role = self.cleaned_data.get('userrole')
        if not role or role == '':
            raise ValidationError("يرجى اختيار نوع الحساب.")
        return role

    def clean_password(self):
        password = self.cleaned_data.get('password')
        try:
            validate_password(password)
        except ValidationError as e:
            # ترجمة الرسائل الإنجليزية إلى العربية
            arabic_errors = _translate_password_errors(list(e.messages))
            raise ValidationError(arabic_errors)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "تأكيد كلمة المرور لا يطابق الكلمة المدخلة.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.username = user.username.lower()
        user.email = user.email.lower()
        if commit:
            user.save()
        return user