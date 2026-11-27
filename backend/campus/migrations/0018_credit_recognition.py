import django.db.models.deletion
from django.conf import settings
from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[('campus','0017_provider_security_sla'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='CreditRecognition',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('source_institution',models.CharField(max_length=200)),('source_reference',models.CharField(max_length=100)),
        ('evidence_url',models.URLField(blank=True)),('credits',models.PositiveSmallIntegerField()),
        ('status',models.CharField(max_length=20,choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')],default='pending')),
        ('review_note',models.CharField(max_length=500,blank=True)),('created_at',models.DateTimeField(auto_now_add=True)),
        ('student',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.student')),
        ('course',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.academiccourse')),
        ('reviewed_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,to=settings.AUTH_USER_MODEL)),
    ],options={'constraints':[models.UniqueConstraint(fields=('student','source_reference'),name='unique_credit_source_reference'),models.CheckConstraint(condition=models.Q(credits__gt=0),name='positive_recognition_credits')]})]
