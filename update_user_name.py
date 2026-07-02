#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from learning.models import User

# تحديث اسم الطالب إلى اسم عربي
user = User.objects.filter(username='teststudent').first()
if user:
    old_name = user.fullname
    user.fullname = 'محمد أحمد'
    user.save()
    print(f"✅ تم تحديث الاسم من: {old_name} إلى: {user.fullname}")
else:
    print("❌ المستخدم غير موجود")
