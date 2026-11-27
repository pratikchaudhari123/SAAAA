import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[('campus','0016_support_accreditation_exam_preparation'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='GatewayOrder',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('reference',models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
            ('amount_paise',models.PositiveBigIntegerField()),('provider_order',models.CharField(max_length=80,unique=True)),
            ('provider_payment',models.CharField(max_length=80,null=True,blank=True,unique=True)),
            ('status',models.CharField(max_length=20,choices=[('created','Created'),('captured','Test capture verified'),('expired','Expired locally')],default='created')),
            ('created_at',models.DateTimeField(auto_now_add=True)),('verified_at',models.DateTimeField(null=True,blank=True)),
            ('account',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.feeaccount')),
            ('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='TallySnapshot',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('company',models.CharField(max_length=200)),('rows',models.JSONField(default=list)),('sha256',models.CharField(max_length=64)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('institution',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.institution')),('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='RequestAudit',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('method',models.CharField(max_length=10)),('path',models.CharField(max_length=500)),('ip',models.GenericIPAddressField(null=True,blank=True)),('status',models.PositiveSmallIntegerField()),('created_at',models.DateTimeField(auto_now_add=True)),
            ('institution',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.institution')),('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='SupportEscalation',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('kind',models.CharField(max_length=20,choices=[('response','Response overdue'),('resolution','Resolution overdue')])),('created_at',models.DateTimeField(auto_now_add=True)),
            ('ticket',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='escalations',to='campus.supportticket')),
        ],options={'constraints':[models.UniqueConstraint(fields=('ticket','kind'),name='unique_support_escalation')]}),
    ]
