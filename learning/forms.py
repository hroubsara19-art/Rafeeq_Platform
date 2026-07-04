from django import forms
from .models import Lessoncontent, Subject, Class, VRLesson

class LessonUploadForm(forms.ModelForm):
    class Meta:
        model = Lessoncontent
        fields = ['lessontitle', 'subjectid', 'originaltext']
        
        labels = {
            'lessontitle': 'عنوان الدرس',
            'subjectid': 'المادة الدراسية',
            'originaltext': 'نص الدرس الأصلي',
        }
        
        widgets = {
            'lessontitle': forms.TextInput(attrs={
                'class': 'form-control form-control-lg shadow-sm', 
                'placeholder': 'مثلاً: رحلة في الجهاز الهضمي'
            }),
            'subjectid': forms.Select(attrs={
                'class': 'form-select shadow-sm'
            }),
            'originaltext': forms.Textarea(attrs={
                'class': 'form-control shadow-sm', 
                'rows': 8, 
                'placeholder': 'ضع النص المعقد هنا ليقوم Gemini بتبسيطه...'
            }),
        }

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        if teacher:
            self.fields['subjectid'].queryset = Subject.objects.filter(teacherid=teacher)


class VRLessonSetupForm(forms.Form):
    """نموذج لإعداد تجربة واقع افتراضي للدرس"""
    
    classroom = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg shadow-sm',
            'id': 'id_classroom',
        }),
        label='اختر الصف الدراسي'
    )
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg shadow-sm',
            'id': 'id_subject',
        }),
        label='اختر المادة الدراسية'
    )
    
    lesson = forms.ModelChoiceField(
        queryset=Lessoncontent.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg shadow-sm',
            'id': 'id_lesson',
        }),
        label='اختر الدرس'
    )
    
    vr_url = forms.URLField(
        widget=forms.URLInput(attrs={
            'class': 'form-control form-control-lg shadow-sm',
            'placeholder': 'ضع رابط موقع الواقع الافتراضي المصمم هنا (اختياري)',
            'dir': 'ltr',
        }),
        label='رابط موقع الواقع الافتراضي (اختياري)',
        required=False,
        help_text='أدخل الرابط الكامل للموقع الذي صممته في منصة Google AI Studio. إذا ترك فارغاً، سيتم استخدام الرابط الافتراضي.'
    )

    vr_attachment = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control form-control-lg shadow-sm',
        }),
        label='مرفق إضافي (اختياري)',
        required=False,
        help_text='ارفق ملفاً إضافياً (PDF, ZIP, أو أي ملف آخر) ليتم إرساله للطالب'
    )
    
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        if teacher:
            # فلتر المواد والدروس حسب المعلم
            self.fields['subject'].queryset = Subject.objects.filter(teacherid=teacher)
            # فلتر الدروس المنشورة فقط
            self.fields['lesson'].queryset = Lessoncontent.objects.filter(teacherid=teacher, status='Published')
            # فلتر الصفوف حسب الصفوف المسندة للمعلم
            from django.db.models import Q
            self.fields['classroom'].queryset = Class.objects.filter(
                Q(subject__teacherid=teacher) | Q(teachers=teacher)
            ).distinct()


class VRLessonForm(forms.ModelForm):
    """نموذج Django لحفظ بيانات الواقع الافتراضي"""
    
    class Meta:
        model = VRLesson
        fields = ['lesson', 'classroom', 'subject', 'vr_url', 'is_published']
        
        labels = {
            'lesson': 'الدرس',
            'classroom': 'الصف الدراسي',
            'subject': 'المادة الدراسية',
            'vr_url': 'رابط الواقع الافتراضي',
            'is_published': 'نشر للطالب',
        }
        
        widgets = {
            'lesson': forms.Select(attrs={
                'class': 'form-select form-select-lg shadow-sm',
            }),
            'classroom': forms.Select(attrs={
                'class': 'form-select form-select-lg shadow-sm',
            }),
            'subject': forms.Select(attrs={
                'class': 'form-select form-select-lg shadow-sm',
            }),
            'vr_url': forms.URLInput(attrs={
                'class': 'form-control form-control-lg shadow-sm',
                'placeholder': 'https://example.com/vr-experience',
                'dir': 'ltr',
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }