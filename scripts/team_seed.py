"""Run only on a local evaluation database through Django manage.py shell.
Creates a separate synthetic institution, prints private credentials to stdout.
Never loads external or real institutional data.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
import secrets
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from campus.models import (Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,Classroom,CourseOffering,CourseEnrollment,LectureSession,SessionAttendance,CourseExam,ExamApplication,FeeAccount,FeeReceipt,HostelBed,HostelCheck,AuditEvent)

tag=secrets.token_hex(4)
credentials=[]
with transaction.atomic():
    i=Institution.objects.create(name='SAAAA Team Evaluation (Synthetic)',slug='team-demo-'+tag)
    members={}
    for role in ('admin','principal','admissions','faculty','finance','warden','coe','student','viewer'):
        username='team_'+tag+'_'+role
        password=secrets.token_urlsafe(18)
        u=get_user_model().objects.create_user(username=username,password=password)
        members[role]=Membership.objects.create(institution=i,user=u,role=role)
        credentials.append((role,username,password))
    admin=members['admin'].user
    today=timezone.localdate()
    dep=Department.objects.create(institution=i,code='CSE',name='Computer Engineering')
    prog=AcademicProgram.objects.create(department=dep,code='BE-CSE',name='Computer Engineering',duration_years=4,intake=60)
    course=AcademicCourse.objects.create(program=prog,code='CS101',name='Programming Fundamentals',semester=1,credits=3)
    period=AcademicPeriod.objects.create(institution=i,code='DEMO-TERM',starts=today-timedelta(days=30),ends=today+timedelta(days=90))
    room=Classroom.objects.create(institution=i,code='LAB-101',capacity=40)
    offering=CourseOffering.objects.create(course=course,period=period,faculty=members['faculty'],batch='A')
    roster=[]
    for n in range(1,13):
        student=Student.objects.create(institution=i,student_id=f'TEAM-{n:03d}',name=f'Example Student {n:02d}',email=f'student{n}@example.invalid',program=prog.name,year=1,status='Pending' if n==12 else 'Active',portal_user=members['student'].user if n==1 else None)
        if student.status=='Active':
            roster.append(CourseEnrollment.objects.create(offering=offering,student=student))
    for n in range(3):
        start=timezone.make_aware(datetime.combine(today-timedelta(days=1),time(9+n)))
        session=LectureSession.objects.create(offering=offering,room=room,starts=start,ends=start+timedelta(minutes=45))
        for e in roster:
            SessionAttendance.objects.create(session=session,enrollment=e,present=(e.pk==roster[0].pk or n!=2),actor=members['faculty'].user)
    start=timezone.make_aware(datetime.combine(today+timedelta(days=1),time(10)))
    LectureSession.objects.create(offering=offering,room=room,starts=start,ends=start+timedelta(minutes=45))
    exam=CourseExam.objects.create(offering=offering,title='Programming assessment',kind='regular',day=today,maximum=100,passing=40,min_attendance=75)
    ExamApplication.objects.create(exam=exam,enrollment=roster[0])
    for n,e in enumerate(roster[:4],1):
        a=FeeAccount.objects.create(student=e.student,period=period.code,assessed=Decimal('10000.00'))
        FeeReceipt.objects.create(account=a,reference=uuid4(),amount=Decimal('4000.00'),method='bank',recorded_by=members['finance'].user)
        b=HostelBed.objects.create(institution=i,code=f'H1-10{n}-A',student=e.student)
        HostelCheck.objects.create(bed=b,student=e.student,day=today,status='present',recorded_by=members['warden'].user)
    AuditEvent.objects.create(institution=i,actor=admin,action='team.demo.seed',target=i.slug)
print('SYNTHETIC TEAM DEMO ONLY')
print('Institution:',i.slug)
for role,username,password in credentials:
    print(role,username,password,sep=' | ')
