"""
يملأ رقم واتساب لكل حساب تركه فارغًا — برقم الحساب نفسه.

**هذا ليس تغييرًا في المعنى.** الحقل كان اختياريًا ومعناه في الكود: «فارغ =
واتسابه على رقم حسابه» (`User.contact_number` يرجع إلى `phone` عند الفراغ).
والترحيلة تكتب صراحةً ما كان الكود يفعله ضمنًا.

ولزم أن يُكتب صراحةً لأن رقم واتساب صار قناة استعادة كلمة المرور: قيمة ضمنية
في خاصية بايثون لا يستطيع استعلام SQL أن يجدها، ولا لوحة الإدارة أن تعرضها،
ولا نحن أن نبني عليها حدّ إرسال.

**التطبيق منشور والحسابات حقيقية**، فالعملية تجري على دفعات ولا تلمس صفًّا
فيه قيمة أصلًا. والتراجع يُبقي كل شيء كما هو — لا نُفرغ حقلًا ملأناه.
"""

from django.db import migrations
from django.db.models import F


def fill_from_account_phone(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(whatsapp_number="").update(whatsapp_number=F("phone"))


def noop(apps, schema_editor):
    """
    التراجع لا يُفرغ شيئًا.

    لا نعرف أي صفّ كان فارغًا قبل الترحيلة وأيّها كتبه صاحبه بيده، وإفراغ
    الكل كان سيمحو أرقامًا حقيقية. الصفّ الممتلئ لا يضرّ أي نسخة سابقة من
    الكود: `contact_number` كان يقرأه قبل هذه الترحيلة وبعدها سواء.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_password_changed_at_alter_user_whatsapp_number_and_more"),
    ]

    operations = [
        migrations.RunPython(fill_from_account_phone, noop),
    ]
