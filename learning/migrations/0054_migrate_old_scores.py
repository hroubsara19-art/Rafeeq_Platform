# Migration to migrate old scores to new fields

from django.db import migrations

def migrate_old_scores(apps, schema_editor):
    """Copy old score values to new fields for existing records."""
    Testattempt = apps.get_model('learning', 'Testattempt')
    
    # Update records where current_score is null but score exists
    for attempt in Testattempt.objects.filter(current_score__isnull=True):
        if attempt.score is not None:
            attempt.current_score = attempt.score
            attempt.first_attempt_score = attempt.score
            attempt.save(update_fields=['current_score', 'first_attempt_score'])

class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0053_dual_view_assessment'),
    ]

    operations = [
        migrations.RunPython(migrate_old_scores, migrations.RunPython.noop),
    ]
