# Script to clean up partial checkpoint migration artifacts
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adhd_learning_system.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Drop the index if it exists
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_chk_lesson_para")
        print("Dropped index idx_chk_lesson_para")
    except Exception as e:
        print(f"Error dropping idx_chk_lesson_para: {e}")
    
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_chk_lesson")
        print("Dropped index idx_chk_lesson")
    except Exception as e:
        print(f"Error dropping idx_chk_lesson: {e}")
    
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_stud_chk_ans")
        print("Dropped index idx_stud_chk_ans")
    except Exception as e:
        print(f"Error dropping idx_stud_chk_ans: {e}")
    
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_chk_ans_chk")
        print("Dropped index idx_chk_ans_chk")
    except Exception as e:
        print(f"Error dropping idx_chk_ans_chk: {e}")
    
    try:
        cursor.execute("DROP INDEX IF EXISTS idx_chk_ans_sess")
        print("Dropped index idx_chk_ans_sess")
    except Exception as e:
        print(f"Error dropping idx_chk_ans_sess: {e}")
    
    # Drop the tables if they exist
    try:
        cursor.execute("DROP TABLE IF EXISTS learning_studentcheckpointanswer CASCADE")
        print("Dropped table learning_studentcheckpointanswer")
    except Exception as e:
        print(f"Error dropping learning_studentcheckpointanswer: {e}")
    
    try:
        cursor.execute("DROP TABLE IF EXISTS learning_checkpoint CASCADE")
        print("Dropped table learning_checkpoint")
    except Exception as e:
        print(f"Error dropping learning_checkpoint: {e}")

print("Cleanup complete. Now run: python manage.py migrate learning 0036")
