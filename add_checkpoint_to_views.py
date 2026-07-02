# Script to add checkpoint data to lesson_result view
import re

with open('learning/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the pattern and insert checkpoint data
pattern = r"(            timing_url = candidate\n\n)(    return render\(request, 'learning/lesson_result\.html', \{)"
replacement = r"""\1    # جلب نقاط التحقق للدرس
    checkpoints = Checkpoint.objects.filter(lessonid=lesson).order_by('paragraph_index')
    checkpoint_data = []
    for cp in checkpoints:
        checkpoint_data.append({
            'checkpoint_id': cp.checkpointid,
            'paragraph_index': cp.paragraph_index,
            'question': cp.question,
            'option_a': cp.option_a,
            'option_b': cp.option_b,
            'correct_answer': cp.correct_answer,
        })

\2"""

new_content = re.sub(pattern, replacement, content)

# Also add 'checkpoints': checkpoint_data to the render call
render_pattern = r"(    return render\(request, 'learning/lesson_result\.html', \{)([^}]+)(\})"
render_replacement = r"\1\2,\n        'checkpoints': checkpoint_data,\3"

new_content = re.sub(render_pattern, render_replacement, new_content)

with open('learning/views.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully added checkpoint data to lesson_result view")
