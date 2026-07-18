# Generated migration for VRLesson model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0047_lessoncontent_video_published_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VRLesson',
            fields=[
                ('vr_id', models.AutoField(db_column='VR_ID', primary_key=True, serialize=False)),
                ('vr_url', models.URLField(db_column='VR_URL', help_text='رابط منصة الواقع الافتراضي المصمم من قبل المعلم', max_length=1000)),
                ('design_platform_url', models.URLField(db_column='DesignPlatformURL', default='https://ai.studio/apps/ea0032ea-b331-4cc8-a5fd-e59bbce58fbe?fullscreenApplet=true', help_text='رابط منصة تصميم بيئة الواقع الافتراضي', max_length=1000)),
                ('is_published', models.BooleanField(db_column='IsPublished', default=False, help_text='هل تم نشر تجربة الواقع الافتراضي للطالب؟')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='CreatedAt')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='UpdatedAt')),
                ('classroom', models.ForeignKey(blank=True, db_column='ClassID', null=True, on_delete=django.db.models.deletion.SET_NULL, to='learning.class')),
                ('lesson', models.OneToOneField(db_column='LessonID', on_delete=django.db.models.deletion.CASCADE, related_name='vr_experience', to='learning.lessoncontent')),
                ('subject', models.ForeignKey(blank=True, db_column='SubjectID', null=True, on_delete=django.db.models.deletion.SET_NULL, to='learning.subject')),
                ('teacher', models.ForeignKey(db_column='TeacherID', on_delete=django.db.models.deletion.CASCADE, to='learning.teacher')),
            ],
            options={
                'db_table': 'VRLesson',
                'managed': True,
            },
        ),
        migrations.AddIndex(
            model_name='vrlesson',
            index=models.Index(fields=['teacher'], name='idx_vr_teacher'),
        ),
        migrations.AddIndex(
            model_name='vrlesson',
            index=models.Index(fields=['classroom'], name='idx_vr_classroom'),
        ),
        migrations.AddIndex(
            model_name='vrlesson',
            index=models.Index(fields=['is_published'], name='idx_vr_published'),
        ),
        migrations.AddIndex(
            model_name='vrlesson',
            index=models.Index(fields=['lesson'], name='idx_vr_lesson'),
        ),
    ]
