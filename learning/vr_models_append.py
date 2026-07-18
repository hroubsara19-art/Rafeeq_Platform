
# ════════════════════════════════════════════════════════════════
# VRLesson
# ════════════════════════════════════════════════════════════════
class VRLesson(models.Model):
    """
    نموذج تخزين تجارب الواقع الافتراضي المرتبطة بالدروس
    - يربط كل درس بتجربة واقع افتراضي فريدة
    - يحتفظ برابط منصة التصميم والرابط النهائي للطالب
    """
    vr_id = models.AutoField(db_column='VR_ID', primary_key=True)
    lesson = models.OneToOneField(
        'Lessoncontent',
        on_delete=models.CASCADE,
        db_column='LessonID',
        related_name='vr_experience'
    )
    teacher = models.ForeignKey(
        'Teacher',
        on_delete=models.CASCADE,
        db_column='TeacherID'
    )
    subject = models.ForeignKey(
        'Subject',
        on_delete=models.SET_NULL,
        db_column='SubjectID',
        null=True,
        blank=True
    )
    classroom = models.ForeignKey(
        'Class',
        on_delete=models.SET_NULL,
        db_column='ClassID',
        null=True,
        blank=True
    )
    vr_url = models.URLField(
        db_column='VR_URL',
        max_length=1000,
        help_text='رابط منصة الواقع الافتراضي المصمم من قبل المعلم'
    )
    design_platform_url = models.URLField(
        db_column='DesignPlatformURL',
        default='https://ai.studio/apps/ea0032ea-b331-4cc8-a5fd-e59bbce58fbe?fullscreenApplet=true',
        max_length=1000,
        help_text='رابط منصة تصميم بيئة الواقع الافتراضي'
    )
    is_published = models.BooleanField(
        db_column='IsPublished',
        default=False,
        help_text='هل تم نشر تجربة الواقع الافتراضي للطالب؟'
    )
    created_at = models.DateTimeField(
        db_column='CreatedAt',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        db_column='UpdatedAt',
        auto_now=True
    )
    
    class Meta:
        managed = True
        db_table = 'VRLesson'
        indexes = [
            models.Index(fields=['teacher'], name='idx_vr_teacher'),
            models.Index(fields=['classroom'], name='idx_vr_classroom'),
            models.Index(fields=['is_published'], name='idx_vr_published'),
            models.Index(fields=['lesson'], name='idx_vr_lesson'),
        ]
    
    def __str__(self):
        return f"VR: {self.lesson.lessontitle} - {self.teacher.userid.fullname}"
