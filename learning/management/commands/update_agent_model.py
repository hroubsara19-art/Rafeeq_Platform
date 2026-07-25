"""
learning/management/commands/update_agent_model.py
════════════════════════════════════════════════════
أمر إدارة Django لتحديث حقل `version` في AiAgent (أو أي وكيل نشط)
إلى موديل صالح وحديث بدل الأسماء المتقاعدة (مثل gemini-2.5-flash
التي أصبحت 404 لحسابات المشاريع الجديدة).

الاستخدام:
    # تحديث كل الوكلاء النشطين إلى القيمة الافتراضية (gemini-flash-latest)
    python manage.py update_agent_model

    # تحديد موديل مختلف
    python manage.py update_agent_model --model gemini-2.5-flash-lite

    # تحديث وكيل واحد فقط بالـ id
    python manage.py update_agent_model --agent-id 3

    # عرض القيم الحالية فقط بدون تعديل (dry-run)
    python manage.py update_agent_model --dry-run
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'يحدّث حقل version في AiAgent إلى موديل Gemini صالح وحديث'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='gemini-flash-latest',
            help='اسم الموديل الجديد (افتراضي: gemini-flash-latest)',
        )
        parser.add_argument(
            '--agent-id',
            type=int,
            default=None,
            help='تحديث وكيل واحد بالـ id بدل كل الوكلاء النشطين',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='عرض القيم الحالية فقط دون حفظ أي تعديل',
        )

    def handle(self, *args, **options):
        from learning.models import AiAgent

        new_model = options['model']
        agent_id  = options['agent_id']
        dry_run   = options['dry_run']

        if agent_id is not None:
            agents = AiAgent.objects.filter(pk=agent_id)
        else:
            agents = AiAgent.objects.filter(isactive=True)

        count = agents.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('لا يوجد وكلاء مطابقين للشرط.'))
            return

        self.stdout.write(f'تم إيجاد {count} وكيل/وكلاء:')
        for agent in agents:
            old_version = getattr(agent, 'version', '') or '(فارغ)'
            # ✅ [FIX] استخدام agent.pk بدل agent.id — بعض الموديلات (مثل AiAgent هنا)
            # تُعرّف مفتاحاً أساسياً باسم مخصص (مثل agentid) بدل id الافتراضي،
            # فـ Django لا ينشئ حقل id تلقائياً في هذه الحالة. pk يعمل دائماً
            # بغض النظر عن اسم الحقل الفعلي المُعرَّف كـ primary_key=True.
            self.stdout.write(
                f'  • pk={agent.pk}  الاسم={getattr(agent, "name", "")!r}  '
                f'الموديل الحالي={old_version!r}'
            )

        if dry_run:
            self.stdout.write(self.style.NOTICE('\n--dry-run: لم يتم أي تعديل.'))
            return

        updated = agents.update(version=new_model)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ تم تحديث {updated} وكيل/وكلاء إلى version={new_model!r}'
            )
        )