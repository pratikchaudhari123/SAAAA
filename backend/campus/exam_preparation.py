"""Exam room allocation and controlled evaluation hall tickets."""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from rest_framework.response import Response
from .models import Institution,Classroom,ExaminationSchedule,ExaminationSeat,ExamApplication,LectureSession
from .academic_engine import member,exams,applications,get,parse,log,eligible
class Allocate(serializers.Serializer):
    exam=serializers.IntegerField(min_value=1)
    rooms=serializers.ListField(child=serializers.IntegerField(min_value=1),min_length=1,max_length=50)
    starts=serializers.DateTimeField()
    ends=serializers.DateTimeField()
class Release(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    confirmed=serializers.BooleanField()
def schedules(m):return ExaminationSchedule.objects.filter(exam__in=exams(m))
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','coe','student'])
    q=schedules(m)
    ss=ExaminationSeat.objects.filter(schedule__in=q,application__in=applications(m),room__institution=m.institution)
    if m.role=='student':ss=ss.filter(schedule__released_at__isnull=False,application__enrollment__student__status='Active')
    data={'seats':list(ss.order_by('schedule__starts','room__code','seat_number').values('id','serial','schedule_id','schedule__starts','schedule__ends','schedule__exam__title','schedule__exam__offering__course__code','schedule__released_at','room__code','seat_number','application__enrollment__student__name','application__enrollment__student__student_id')),'institution':m.institution.name}
    if m.role!='student':
        data['exams']=list(exams(m).filter(status='closed',day__gte=timezone.localdate()).values('id','title','day','offering__course__code'))
        data['rooms']=list(Classroom.objects.filter(institution=m.institution).values('id','code','capacity'))
        data['schedules']=list(q.order_by('-starts').values('id','exam__title','starts','ends','released_at'))
    response=Response(data);response['Cache-Control']='private, no-store';return response
@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','coe'])
    schemas={'allocate':Allocate,'release':Release}
    if action not in schemas:raise NotFound()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='allocate':
            exam=get(exams(m),d['exam'])
            starts,ends=d['starts'],d['ends']
            if exam.status!='closed' or starts<=timezone.now() or ends<=starts or timezone.localdate(starts)!=exam.day or timezone.localdate(ends)!=exam.day:raise ValidationError('Closed application window and future times on examination date required.')
            if schedules(m).filter(exam=exam).exists():raise ValidationError('Exam already allocated.')
            rooms=list(Classroom.objects.filter(institution=m.institution,pk__in=d['rooms']).order_by('code','pk'))
            if len(rooms)!=len(d['rooms']):raise ValidationError('Select distinct rooms in this institution.')
            apps=list(ExamApplication.objects.filter(exam=exam,enrollment__student__institution=m.institution).select_related('enrollment__student').order_by('enrollment__student__student_id','pk'))
            if not apps or any(not eligible(exam,a.enrollment) for a in apps):raise ValidationError('All applicants must be eligible.')
            if sum(r.capacity for r in rooms)<len(apps):raise ValidationError('Room capacity insufficient.')
            conflicts=ExaminationSeat.objects.filter(schedule__in=schedules(m),schedule__starts__lt=ends,schedule__ends__gt=starts)
            if conflicts.filter(room__in=rooms).exists() or conflicts.filter(application__enrollment__student_id__in=[a.enrollment.student_id for a in apps]).exists():raise ValidationError('Exam room or student time conflict.')
            lectures=LectureSession.objects.filter(offering__period__institution=m.institution,starts__lt=ends,ends__gt=starts)
            if lectures.filter(room__in=rooms).exists() or lectures.filter(offering__enrollments__student_id__in=[a.enrollment.student_id for a in apps]).exists():raise ValidationError('Conflicts with scheduled teaching.')
            row=ExaminationSchedule.objects.create(exam=exam,starts=starts,ends=ends,created_by=m.user)
            seats=[];index=0
            for room in rooms:
                for number in range(1,room.capacity+1):
                    if index>=len(apps):break
                    seats.append(ExaminationSeat(schedule=row,application=apps[index],room=room,seat_number=number));index+=1
            ExaminationSeat.objects.bulk_create(seats)
        else:
            row=get(schedules(m),d['id'])
            if not d['confirmed'] or row.released_at or row.starts<=timezone.now() or row.exam.status!='closed':raise ValidationError('Only unreleased future closed exams may be released.')
            if any(not eligible(row.exam,s.application.enrollment) for s in row.seats.select_related('application__enrollment__student')):raise ValidationError('Student eligibility changed; review allocation.')
            row.released_at=timezone.now();row.save(update_fields=['released_at'])
        log(m,'exam-prep.'+action,row)
    return Response({'id':row.pk},status=201)
