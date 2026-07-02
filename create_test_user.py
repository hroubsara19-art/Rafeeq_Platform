#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from learning.models import User
from learning.models import Learningsession

# Create test student if doesn't exist
user, created = User.objects.get_or_create(
    username='teststudent',
    defaults={'fullname': 'Test Student', 'email': 'test@example.com'}
)

if created:
    user.set_password('testpass123')
    user.save()
    print(f"Created user: {user.username}")
else:
    # Update password anyway to ensure it's correct
    user.set_password('testpass123')
    user.save()
    print(f"User already exists, password updated: {user.username}")

print(f"Test user ready: username=teststudent, password=testpass123")
