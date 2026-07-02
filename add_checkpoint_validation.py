# Script to add checkpoint validation to publish_lesson view
import re

with open('learning/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the publish_lesson function and add checkpoint validation
# Look for the section where it checks if updated_text exists
pattern = r"(    if request\.method == 'POST':\n        updated_text = request\.POST\.get\('updated_text', ''\)\.strip\(\)\n        if updated_text:\n            clean = _sanitize_text\(updated_text\)\n            lesson\.ai_generatedtext = clean\n            lesson\.status = STATUS_PUBLISHED)"

replacement = r"""    if request.method == 'POST':
        updated_text = request.POST.get('updated_text', '').strip()
        if updated_text:
            # ✅ التحقق من وجود نقطة تحقق واحدة على الأقل قبل النشر
            checkpoint_count = Checkpoint.objects.filter(lessonid=lesson).count()
            if checkpoint_count == 0:
                messages.error(request, 'يجب إضافة نقطة تحقق واحدة على الأقل للدرس قبل نشره.')
                return redirect('learning:lesson_result', lesson_id=lesson.pk)
            
            clean = _sanitize_text(updated_text)
            lesson.ai_generatedtext = clean
            lesson.status = STATUS_PUBLISHED"""

new_content = re.sub(pattern, replacement, content)

with open('learning/views.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully added checkpoint validation to publish_lesson view")
