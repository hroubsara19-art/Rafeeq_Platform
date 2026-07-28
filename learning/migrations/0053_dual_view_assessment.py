# Generated migration for Dual-View Assessment

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0052_lessoncontent_video_published'),
    ]

    operations = [
        # === TestAttempt modifications ===
        migrations.AddField(
            model_name='testattempt',
            name='first_attempt_score',
            field=models.IntegerField(null=True, blank=True, help_text='علامة المحاولة الأولى الحقيقية (للمعلم فقط)', db_column='FirstAttemptScore'),
        ),
        migrations.AddField(
            model_name='testattempt',
            name='current_score',
            field=models.IntegerField(null=True, blank=True, help_text='العلامة الحالية بعد جميع المحاولات', db_column='CurrentScore'),
        ),
        migrations.AddField(
            model_name='testattempt',
            name='total_attempts',
            field=models.IntegerField(default=1, help_text='عدد المحاولات الكلي', db_column='TotalAttempts'),
        ),
        migrations.AddField(
            model_name='testattempt',
            name='progress_percentage',
            field=models.IntegerField(default=0, help_text='نسبة التقدم للطالب (0-100)', db_column='ProgressPercentage'),
        ),
        migrations.AddField(
            model_name='testattempt',
            name='is_completed',
            field=models.BooleanField(default=False, help_text='هل أكمل الطالب التقييم؟', db_column='IsCompleted'),
        ),
        migrations.AddField(
            model_name='testattempt',
            name='stars_earned',
            field=models.IntegerField(default=0, help_text='عدد النجوم المكتسبة', db_column='StarsEarned'),
        ),
        migrations.AddField(
            model_name='testattempt',
            name='last_retry_date',
            field=models.DateTimeField(blank=True, null=True, help_text='تاريخ آخر محاولة إعادة', db_column='LastRetryDate'),
        ),
        
        # === StudentAnswer modifications ===
        migrations.AddField(
            model_name='studentanswer',
            name='attempt_number',
            field=models.IntegerField(default=1, help_text='رقم المحاولة لهذا السؤال', db_column='AttemptNumber'),
        ),
        migrations.AddField(
            model_name='studentanswer',
            name='needs_retry',
            field=models.BooleanField(default=False, help_text='هل يحتاج السؤال لإعادة المحاولة؟', db_column='NeedsRetry'),
        ),
        migrations.AddField(
            model_name='studentanswer',
            name='is_mastered',
            field=models.BooleanField(default=False, help_text='هل أتقن الطالب هذا السؤال؟', db_column='IsMastered'),
        ),
        
        # === Add indexes ===
        migrations.AddIndex(
            model_name='testattempt',
            index=models.Index(fields=['studentid', '-attemptdate'], name='idx_attempt_student_date'),
        ),
        migrations.AddIndex(
            model_name='studentanswer',
            index=models.Index(fields=['attemptid', 'questionid'], name='idx_answer_attempt_question'),
        ),
    ]
