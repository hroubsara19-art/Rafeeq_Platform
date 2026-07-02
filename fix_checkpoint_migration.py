# Script to remove the checkpoint migration record and re-apply it
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Remove the migration record
    cursor.execute(
        "DELETE FROM django_migrations WHERE app = 'learning' AND name = '0036_checkpoint_studentcheckpointanswer_and_more'"
    )
    print("Migration record removed from django_migrations table")

print("Now run: python manage.py migrate learning 0036")
