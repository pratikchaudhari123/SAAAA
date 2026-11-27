"""Relational academic and examination pilot. All mutations are tenant scoped."""
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import (Institution, Membership, Student, AcademicCourse, AcademicPeriod, Classroom,
    CourseOffering, CourseEnrollment, LectureSession, SessionAttendance, CourseExam, ExamApplication, AuditEvent)

class RoomInput(serializers.Serializer):
    code=serializers.CharField(max_length=40)
    capacity=serializers.IntegerField(min_value=1,max_value=1000)
class OfferingInput(serializers.Serializer):
    course=serializers.IntegerField(min_value=1)
    period=serializers.IntegerField(min_value=1)
    faculty=serializers.IntegerField(min_value=1)
    batch=serializers.CharField(max_length=40)
class EnrollmentInput(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    student_id=serializers.CharField(max_length=50)
class SessionInput(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    room=serializers.IntegerField(min_value=1)
    starts=serializers.DateTimeField()
    ends=serializers.DateTimeField()
class AttendanceInput(serializers.Serializer):
    session=serializers.IntegerField(min_value=1)
    enrollment=serializers.IntegerField(min_value=1)
    present=serializers.BooleanField()
class ExamInput(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=100)
    kind=serializers.ChoiceField(choices=['regular','backlog','makeup'])
    day=serializers.DateField()
    maximum=serializers.IntegerField(min_value=1,max_value=1000)
    passing=serializers.IntegerField(min_value=1,max_value=1000)
    min_attendance=serializers.IntegerField(min_value=0,max_value=100)
class ApplicationInput(serializers.Serializer):
    exam=serializers.IntegerField(min_value=1)
    enrollment=serializers.IntegerField(min_value=1)
class ExamStateInput(serializers.Serializer):
    exam=serializers.IntegerField(min_value=1)
    status=serializers.ChoiceField(choices=['closed','published'])
class MarksInput(serializers.Serializer):
    application=serializers.IntegerField(min_value=1)
    marks=serializers.IntegerField(min_value=0,max_value=1000)

def member(request,slug,roles):
    m=Membership.objects.filter(user=request.user,institution__slug=slug,role__in=roles).first()
    if not m: raise PermissionDenied()
    return m

def offerings(m):
    q=CourseOffering.objects.filter(course__program__department__institution=m.institution,period__institution=m.institution,faculty__institution=m.institution)
    if m.role=='faculty': q=q.filter(faculty=m)
    if m.role=='student': q=q.filter(enrollments__student__institution=m.institution,enrollments__student__portal_user=m.user).distinct()
    return q

def get(q,pk):
    row=q.filter(pk=pk).first()
    if row is None: raise NotFound('Record not available in your workspace.')
    return row

def parse(cls,request):
    s=cls(data=request.data)
    s.is_valid(raise_exception=True)
    return s.validated_data

def log(m,action,row):
    AuditEvent.objects.create(institution=m.institution,actor=m.user,action=action,target=str(row.pk))

def enrollments(m):
    q=CourseEnrollment.objects.filter(offering__in=offerings(m),student__institution=m.institution)
    if m.role=='student': q=q.filter(student__portal_user=m.user)
    return q

def sessions(m):
    return LectureSession.objects.filter(offering__in=offerings(m),room__institution=m.institution)

def exams(m):
    return CourseExam.objects.filter(offering__in=offerings(m))

def applications(m):
    return ExamApplication.objects.filter(exam__in=exams(m),enrollment__in=enrollments(m))

@api_view(['GET'])
def academics(request,slug):
    m=member(request,slug,['admin','faculty','coe','student'])
    data={
        'offerings':list(offerings(m).order_by('course__code','batch').values('id','course__code','course__name','period__code','batch','faculty__user__username')),
        'enrollments':list(enrollments(m).order_by('student__student_id').values('id','offering_id','student__student_id','student__name')),
        'sessions':list(sessions(m).order_by('-starts').values('id','offering_id','room__code','starts','ends')),
        'attendance':list(SessionAttendance.objects.filter(session__in=sessions(m),enrollment__in=enrollments(m)).order_by('-session__starts').values('session_id','enrollment_id','present')),
    }
    if m.role=='admin':
        data.update({
            'rooms':list(Classroom.objects.filter(institution=m.institution).order_by('code').values('id','code','capacity')),
            'courses':list(AcademicCourse.objects.filter(program__department__institution=m.institution,active=True,program__active=True,program__department__active=True).values('id','code','name','program__name')),
            'periods':list(AcademicPeriod.objects.filter(institution=m.institution,active=True).values('id','code','starts','ends')),
            'faculty':list(Membership.objects.filter(institution=m.institution,role='faculty',user__is_active=True).values('id','user__username')),
        })
    return Response(data)

@api_view(['POST'])
def academic_action(request,slug,action):
    m=member(request,slug,['admin','faculty'])
    if action!='attendance' and m.role!='admin': raise PermissionDenied()
    schemas={'room':RoomInput,'offering':OfferingInput,'enrollment':EnrollmentInput,'session':SessionInput,'attendance':AttendanceInput}
    if action not in schemas: raise NotFound()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            if action=='room':
                row=Classroom.objects.create(institution=m.institution,**d)
            elif action=='offering':
                c=get(AcademicCourse.objects.filter(program__department__institution=m.institution,active=True,program__active=True,program__department__active=True),d['course'])
                p=get(AcademicPeriod.objects.filter(institution=m.institution,active=True),d['period'])
                f=get(Membership.objects.filter(institution=m.institution,role='faculty',user__is_active=True),d['faculty'])
                row=CourseOffering.objects.create(course=c,period=p,faculty=f,batch=d['batch'])
            elif action=='enrollment':
                o=get(offerings(m),d['offering'])
                s=Student.objects.filter(institution=m.institution,student_id=d['student_id'],status='Active').first()
                if not s: raise ValidationError('Select an active student.')
                # Legacy program is text; require explicit matching rather than silently reassigning it.
                if s.program!=o.course.program.name: raise ValidationError('Student program must match the course program. Verify legacy program mapping first.')
                if (o.course.semester+1)//2!=s.year: raise ValidationError('Course semester does not match student year.')
                count=o.enrollments.count()
                if count>=o.course.program.intake: raise ValidationError('Program intake limit reached for this offering.')
                if LectureSession.objects.filter(offering=o,room__capacity__lte=count).exists(): raise ValidationError('Enrollment exceeds an assigned room capacity.')
                if LectureSession.objects.filter(offering=o,starts__lte=timezone.now()).exists(): raise ValidationError('Enrollment is locked after the first scheduled session starts.')
                row=CourseEnrollment.objects.create(offering=o,student=s)
            elif action=='session':
                o=get(offerings(m),d['offering'])
                room=get(Classroom.objects.filter(institution=m.institution),d['room'])
                starts,ends=d['starts'],d['ends']
                if ends<=starts or timezone.localdate(starts)!=timezone.localdate(ends): raise ValidationError('Choose valid start and end times on the same day.')
                if not o.period.starts<=timezone.localdate(starts)<=o.period.ends: raise ValidationError('Session falls outside academic period.')
                if o.enrollments.count()>room.capacity: raise ValidationError('Classroom capacity exceeded.')
                conflicts=LectureSession.objects.filter(offering__course__program__department__institution=m.institution,starts__lt=ends,ends__gt=starts)
                if conflicts.filter(Q(room=room)|Q(offering__faculty=o.faculty)|Q(offering__course__program=o.course.program,offering__batch=o.batch)).exists(): raise ValidationError('Room, faculty or batch already scheduled.')
                if conflicts.filter(offering__enrollments__student_id__in=o.enrollments.values('student_id')).exists(): raise ValidationError('An enrolled student already has a lecture during this time.')
                row=LectureSession.objects.create(offering=o,room=room,starts=starts,ends=ends)
            else:
                s=get(sessions(m),d['session'])
                e=get(enrollments(m).filter(offering=s.offering,student__status='Active'),d['enrollment'])
                if s.starts>timezone.now(): raise ValidationError('Cannot record attendance before session starts.')
                if CourseExam.objects.filter(offering=s.offering,status__in=['closed','published']).exists(): raise ValidationError('Attendance locked after exam applications close.')
                row,_=SessionAttendance.objects.update_or_create(session=s,enrollment=e,defaults={'present':d['present'],'actor':m.user})
            log(m,'academic.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid academic record.')
    return Response({'id':row.pk},status=201)

@api_view(['GET'])
def examination(request,slug):
    m=member(request,slug,['admin','coe','student'])
    rows=list(applications(m).order_by('exam__day','enrollment__student__student_id').values('id','exam_id','enrollment_id','enrollment__student__student_id','enrollment__student__name','marks','exam__maximum','exam__passing','exam__status'))
    for row in rows:
        if m.role=='student' and row['exam__status']!='published': row['marks']=None
        row['result']=None if row['exam__status']!='published' or row['marks'] is None else ('Pass' if row['marks']>=row['exam__passing'] else 'Fail')
    return Response({'exams':list(exams(m).order_by('-day').values('id','offering_id','offering__course__code','title','kind','day','maximum','passing','min_attendance','status')),'applications':rows})

@api_view(['POST'])
def exam_action(request,slug,action):
    m=member(request,slug,['admin','coe','student'])
    if m.role=='student' and action!='apply': raise PermissionDenied()
    schemas={'create':ExamInput,'apply':ApplicationInput,'state':ExamStateInput,'marks':MarksInput}
    if action not in schemas: raise NotFound()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            if action=='create':
                o=get(offerings(m),d.pop('offering'))
                if d['passing']>d['maximum']: raise ValidationError('Passing marks exceed maximum.')
                if not o.period.starts<=d['day']<=o.period.ends or d['day']<timezone.localdate(): raise ValidationError('Exam must fall within academic period and not be in the past.')
                row=CourseExam.objects.create(offering=o,**d)
            elif action=='apply':
                exam=get(exams(m),d['exam'])
                e=get(enrollments(m).filter(offering=exam.offering,student__status='Active'),d['enrollment'])
                if exam.status!='open' or exam.day<timezone.localdate(): raise ValidationError('Applications are closed.')
                if exam.min_attendance:
                    total=LectureSession.objects.filter(offering=exam.offering,ends__lte=timezone.now()).count()
                    marks=SessionAttendance.objects.filter(enrollment=e,session__offering=exam.offering,session__ends__lte=timezone.now())
                    if not total or marks.count()!=total or marks.filter(present=True).count()*100<exam.min_attendance*total: raise ValidationError('Attendance eligibility not met or attendance records incomplete.')
                row=ExamApplication.objects.create(exam=exam,enrollment=e)
            elif action=='state':
                row=get(exams(m),d['exam'])
                if d['status']=='closed' and row.status=='open': pass
                elif d['status']=='published' and row.status=='closed':
                    if row.day>timezone.localdate() or not row.applications.exists() or row.applications.filter(marks__isnull=True).exists(): raise ValidationError('Exam date or incomplete marks prevent publication.')
                else: raise ValidationError('Invalid examination transition.')
                row.status=d['status']
                row.save(update_fields=['status'])
            else:
                row=get(applications(m),d['application'])
                if row.exam.status!='closed' or row.exam.day>timezone.localdate(): raise ValidationError('Marks require a closed application window and exam date reached.')
                if d['marks']>row.exam.maximum: raise ValidationError('Marks exceed exam maximum.')
                row.marks=d['marks']
                row.save(update_fields=['marks'])
            log(m,'exam.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid examination record.')
    return Response({'id':row.pk},status=201)
