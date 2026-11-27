import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('campus','0015_learningattachment_lectureteachingplan_and_more'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='SupportTicket',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('reference',models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
            ('title',models.CharField(max_length=150)),('description',models.TextField()),
            ('category',models.CharField(max_length=20,choices=[('query','Query'),('incident','Incident'),('change','Change request')])),
            ('status',models.CharField(max_length=20,choices=[('open','Open'),('assigned','Assigned'),('resolved','Resolved'),('closed','Closed')],default='open')),
            ('response_due',models.DateTimeField()),('resolution_due',models.DateTimeField()),
            ('responded_at',models.DateTimeField(null=True,blank=True)),('resolved_at',models.DateTimeField(null=True,blank=True)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('institution',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.institution')),
            ('requester',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='support_requests',to='campus.membership')),
            ('assignee',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name='support_assignments',to='campus.membership')),
        ]),
        migrations.CreateModel(name='SupportTicketEvent',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('action',models.CharField(max_length=20)),('note',models.TextField()),('created_at',models.DateTimeField(auto_now_add=True)),
            ('ticket',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='events',to='campus.supportticket')),
            ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.membership')),
        ]),
        migrations.CreateModel(name='AccreditationEvidence',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('framework',models.CharField(max_length=10,choices=[('NBA','NBA'),('NAAC','NAAC'),('NIRF','NIRF')])),
            ('criterion',models.CharField(max_length=100)),('title',models.CharField(max_length=150)),('description',models.TextField()),('url',models.URLField(blank=True)),
            ('status',models.CharField(max_length=15,choices=[('draft','Draft'),('reviewed','Reviewed')],default='draft')),('created_at',models.DateTimeField(auto_now_add=True)),
            ('period',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.academicperiod')),
            ('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
            ('reviewed_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name='reviewed_accreditation_evidence',to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='ExaminationSchedule',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('starts',models.DateTimeField()),('ends',models.DateTimeField()),('released_at',models.DateTimeField(null=True,blank=True)),
            ('exam',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name='schedule',to='campus.courseexam')),
            ('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ],options={'constraints':[models.CheckConstraint(condition=models.Q(ends__gt=models.F('starts')),name='valid_examination_schedule_times')]}),
        migrations.CreateModel(name='ExaminationSeat',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('seat_number',models.PositiveIntegerField()),('serial',models.UUIDField(default=uuid.uuid4,unique=True,editable=False)),
            ('schedule',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='seats',to='campus.examinationschedule')),
            ('application',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,to='campus.examapplication')),
            ('room',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='campus.classroom')),
        ],options={'constraints':[models.UniqueConstraint(fields=('schedule','room','seat_number'),name='unique_examination_seat'),models.CheckConstraint(condition=models.Q(seat_number__gt=0),name='positive_examination_seat')]}),
    ]
