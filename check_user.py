#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from learning.models import User

user = User.objects.filter(username='teststudent').first()
if user:
    print(f"Username: {user.username}")
    print(f"Full Name (fullname): {user.fullname}")
    print(f"Email: {user.email}")
    print(f"User Role: {user.userrole}")
else:
    print("User not found")
