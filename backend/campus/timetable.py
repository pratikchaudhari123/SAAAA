"""Calendar, deterministic recurring timetable and teaching plans."""
from datetime import datetime,timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from rest_framework.response import Response
from .models import Institution,AcademicPeriod,AcademicCalendarDay,Classroom,LectureSession,LectureTeachingPlan,SessionAttendance
from .academic_engine import member,offerings,sessions,get,parse,log,validate_session

ROLES=['admin','principal','faculty','student']
class Calendar(serializers.Serializer):
    period=serializers.IntegerField(min_value=1)
    day=serializers.DateField()
    title=serializers.CharField(max_length=150)
    kind=serializers.ChoiceField(choices=['holiday','event','academic'])
    blocks_teaching=serializers.BooleanField(default=False)
class Recurring(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    room=serializers.IntegerField(min_value=1)
    first=serializers.DateField()
    last=serializers.DateField()
    weekdays=serializers.ListField(child=serializers.IntegerField(min_value=0,max_value=6),min_length=1,max_length=7)
    starts=serializers.TimeField()
    ends=serializers.TimeField()
    def validate(self,d):
        if d['last']<d['first'] or (d['last']-d['first']).days>183 or d['first']<timezone.localdate(): raise serializers.ValidationError('Choose a future or current date range of at most 184 days.')
        if d['ends']<=d['starts'] or len(set(d['weekdays']))!=len(d['weekdays']): raise serializers.ValidationError('Invalid time range or repeated weekday.')
        return d
class Move(serializers.Serializer):
    session=serializers.IntegerField(min_value=1)
    room=serializers.IntegerField(min_value=1)
    starts=serializers.DateTimeField()
    ends=serializers.DateTimeField()
    reason=serializers.CharField(max_length=300)
class Plan(serializers.Serializer):
    session=serializers.IntegerField(min_value=1)
    topics=serializers.CharField(max_length=6000)
    delivery_note=serializers.CharField(max_length=6000,allow_blank=True,default='')
def periods(m):
    q=AcademicPeriod.objects.filter(institution=m.institution)
    if m.role in ('faculty','student'): q=q.filter(pk__in=offerings(m).values('period_id'))
    return q
def at(day,t):
    return timezone.make_aware(datetime.combine(day,t),timezone.get_current_timezone())
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,ROLES)
    own=sessions(m)
    # Restrict students to their own enrolled course schedules.
    today=timezone.localdate()
    schedule=own.filter(starts__date__gte=today-timedelta(days=7),starts__date__lte=today+timedelta(days=35))
    plans=LectureTeachingPlan.objects.filter(session__in=schedule)
    data={'calendar':list(AcademicCalendarDay.objects.filter(period__in=periods(m)).order_by('day').values('id','period_id','period__code','day','title','kind','blocks_teaching')),
          'periods':list(periods(m).order_by('starts').values('id','code','starts','ends','active')),
          'offerings':list(offerings(m).values('id','course__code','course__name','batch','period_id')),
          'sessions':list(schedule.order_by('starts').values('id','offering_id','offering__course__code','room_id','room__code','starts','ends')),
          'plans':list(plans.values('session_id','topics','delivery_note','updated_at'))}
    if m.role in ('admin','principal'):
        rooms=list(Classroom.objects.filter(institution=m.institution).values('id','code','capacity'))
        data['rooms']=rooms
        occupied=set(own.filter(starts__lte=timezone.now(),ends__gt=timezone.now()).values_list('room_id',flat=True))
        data['occupancy']=[{**r,'occupied_now':r['id'] in occupied} for r in rooms]
    response=Response(data);response['Cache-Control']='private, no-store';return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','faculty'])
    schemas={'calendar':Calendar,'preview':Recurring,'generate':Recurring,'move':Move,'plan':Plan}
    if action not in schemas: raise NotFound()
    if action!='plan' and m.role!='admin': raise PermissionDenied()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='calendar':
            p=get(periods(m),d.pop('period'))
            if not p.active or not p.starts<=d['day']<=p.ends or d['day']<timezone.localdate(): raise ValidationError('Calendar date must be within an active period and not historical.')
            if d['kind']=='holiday': d['blocks_teaching']=True
            if d['blocks_teaching'] and LectureSession.objects.filter(offering__period=p,starts__date=d['day']).exists(): raise ValidationError('Move existing lectures off this date before blocking teaching.')
            if AcademicCalendarDay.objects.filter(period=p,day=d['day']).exists(): raise ValidationError('Calendar date already configured.')
            row=AcademicCalendarDay.objects.create(period=p,created_by=m.user,**d)
        elif action in ('preview','generate'):
            o=get(offerings(m),d['offering'])
            room=get(Classroom.objects.filter(institution=m.institution),d['room'])
            if not(o.period.active and o.course.active and o.course.program.active and o.course.program.department.active and o.faculty.user.is_active and o.faculty.role=='faculty'): raise ValidationError('Offering must be active.')
            if d['first']<o.period.starts or d['last']>o.period.ends: raise ValidationError('Date range must be within the offering period.')
            blocked=set(AcademicCalendarDay.objects.filter(period=o.period,blocks_teaching=True,day__range=(d['first'],d['last'])).values_list('day',flat=True))
            planned=[];skipped=[];existing=[];conflicts=[]
            for offset in range((d['last']-d['first']).days+1):
                day=d['first']+timedelta(days=offset)
                if day.weekday() not in d['weekdays']: continue
                if day in blocked: skipped.append(str(day));continue
                starts=at(day,d['starts']);ends=at(day,d['ends'])
                if LectureSession.objects.filter(offering=o,room=room,starts=starts,ends=ends).exists(): existing.append(str(day));continue
                if starts<=timezone.now(): conflicts.append({'day':str(day),'reason':'Session start is in the past.'});continue
                try: validate_session(m,o,room,starts,ends)
                except ValidationError as e: conflicts.append({'day':str(day),'reason':str(e.detail[0] if isinstance(e.detail,list) else e.detail)});continue
                planned.append((starts,ends))
            result={'planned':[{'starts':s,'ends':e} for s,e in planned],'skipped_holidays':skipped,'existing':existing,'conflicts':conflicts,'created':0}
            if action=='preview': return Response(result)
            if conflicts: raise ValidationError({'conflicts':[str(c['day'])+': '+c['reason'] for c in conflicts]})
            for starts,ends in planned:
                row=LectureSession.objects.create(offering=o,room=room,starts=starts,ends=ends)
                log(m,'timetable.generate',row)
            result['created']=len(planned)
            return Response(result,status=201)
        elif action=='move':
            row=get(sessions(m),d['session'])
            room=get(Classroom.objects.filter(institution=m.institution),d['room'])
            if row.starts<=timezone.now() or d['starts']<=timezone.now() or SessionAttendance.objects.filter(session=row).exists(): raise ValidationError('Only future sessions without attendance can be moved.')
            validate_session(m,row.offering,room,d['starts'],d['ends'],exclude=row.pk)
            # Preserve session identifier and teaching plan, log original and new schedule.
            from .models import AuditEvent
            AuditEvent.objects.create(institution=m.institution,actor=m.user,action='timetable.move.previous',target=str(row.pk)+':'+str(row.room_id)+':'+row.starts.isoformat())
            row.room=room;row.starts=d['starts'];row.ends=d['ends'];row.save(update_fields=['room','starts','ends'])
            from .models import AuditEvent
            AuditEvent.objects.create(institution=m.institution,actor=m.user,action='timetable.move.reason',target=d['reason'][:100])
        else:
            session=get(sessions(m),d.pop('session'))
            if d['delivery_note'] and session.starts>timezone.now(): raise ValidationError('Record teaching delivery after the lecture starts.')
            row,_=LectureTeachingPlan.objects.update_or_create(session=session,defaults={**d,'updated_by':m.user})
        log(m,'timetable.'+action,row)
    return Response({'id':row.pk},status=201)
