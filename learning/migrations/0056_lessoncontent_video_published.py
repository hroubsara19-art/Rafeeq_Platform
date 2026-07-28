# Generated migration to mark video_published as already existing

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0055_remove_testattempt_score_and_more'),
    ]

    operations = [
        # This field already exists in the database, so we do nothing
    ]
