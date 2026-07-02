#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from learning.models import User, Lessoncontent, Class, Subject, Student

# Create test student user
user, created = User.objects.get_or_create(
    username='teststudent',
    defaults={'fullname': 'Test Student', 'email': 'test@example.com'}
)

if created:
    user.set_password('testpass123')
    user.save()
    print(f"Created user: {user.username}")
else:
    user.set_password('testpass123')
    user.save()
    print(f"User updated: {user.username}")

# Get or create a class with the lesson
lesson = Lessoncontent.objects.filter(video_file__isnull=False).exclude(video_file='').first()
if lesson:
    print(f"Using lesson: {lesson.lessontitle}")
    
    # Get the class that contains this lesson's subject
    class_obj = Class.objects.filter(subject=lesson.subjectid).first()
    if not class_obj:
        # Create a test class
        class_obj, _ = Class.objects.get_or_create(
            classname='Test Class',
            defaults={'classdesc': 'Test class for video tracking'}
        )
        if lesson.subjectid:
            class_obj.subject.add(lesson.subjectid)
        print(f"Created/using class: {class_obj.classname}")
    else:
        print(f"Using existing class: {class_obj.classname}")
    
    # Create or get student profile
    student, created = Student.objects.get_or_create(
        userid=user,
        defaults={
            'classid': class_obj,
            'age': 12
        }
    )
    
    if created:
        print(f"Created student profile for {user.username}")
    else:
        print(f"Student profile already exists for {user.username}")
        if student.classid != class_obj:
            student.classid = class_obj
            student.save()
            print(f"Updated class assignment")

print(f"\nTest setup complete!")
print(f"Username: teststudent")
print(f"Password: testpass123")
print(f"Lesson ID: {lesson.pk if lesson else 'N/A'}")
