"""Scheduled notices, personal task acknowledgments, and cohort feedback."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import (Institution, Membership, CampusNotice, NoticeAcknowledgment, FeedbackSurvey,
    FeedbackInvite, FeedbackResponse, Student, CourseEnrollment, LectureSession, SessionAttendance, FeeAccount, FeeReceipt)
from .academic_engine import member, offerings, parse, get, log

INTERNAL=[r[0] for r in Membership._meta.get_field('role').choices if r[0]!='company']
class NoticeInput(serializers.Serializer):
    title=serializers.CharField(max_length=150)
    body=serializers.CharField(max_length=10000)
    kind=serializers.ChoiceField(choices=['notice','memo','news','event','task'])
    audience=serializers.ChoiceField(choices=['all','individual',*INTERNAL])
    recipient=serializers.IntegerField(min_value=1,required=False,allow_null=True,default=None)
    starts=serializers.DateTimeField()
    ends=serializers.DateTimeField()
    link=serializers.URLField(allow_blank=True,required=False,default='')
    def validate(self,d):
        if (d['audience']=='individual') != bool(d['recipient']): raise serializers.ValidationError('Choose a recipient only for individual notices.')
        if d['ends']<=d['starts'] or d['ends']<=timezone.now(): raise serializers.ValidationError('Notice needs a valid future end time.')
        if d['link'] and not d['link'].startswith('https://'): raise serializers.ValidationError('Use HTTPS links.')
        return d
class Ref(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
class SurveyInput(serializers.Serializer):
    title=serializers.CharField(max_length=150)
    kind=serializers.ChoiceField(choices=['academic','teaching','non_teaching','infrastructure','exit'])
    offering=serializers.IntegerField(min_value=1,allow_null=True,required=False,default=None)
    scale=serializers.ChoiceField(choices=['grade','marks'])
    questions=serializers.ListField(child=serializers.CharField(max_length=500),min_length=1,max_length=30)
    opens=serializers.DateTimeField()
    closes=serializers.DateTimeField()
    min_attendance=serializers.IntegerField(min_value=0,max_value=100,default=0)
    min_fee_paid=serializers.IntegerField(min_value=0,max_value=100,default=0)
    def validate(self,d):
        if d['closes']<=d['opens'] or d['closes']<=timezone.now(): raise serializers.ValidationError('Invalid feedback time window.')
        if d['min_attendance'] and not d['offering']: raise serializers.ValidationError('Attendance filter requires a course offering.')
        if d['kind']=='teaching' and not d['offering']: raise serializers.ValidationError('Teaching feedback requires a course offering.')
        if len(set(d['questions']))!=len(d['questions']): raise serializers.ValidationError('Questions must be distinct.')
        return d
class AnswerInput(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    scores=serializers.ListField(child=serializers.IntegerField(min_value=1,max_value=100),min_length=1,max_length=30)

def visible_notices(m):
    now=timezone.now()
    return CampusNotice.objects.filter(institution=m.institution,withdrawn=False,starts__lte=now,ends__gt=now).filter(Q(audience='all')|Q(audience=m.role)|Q(audience='individual',recipient=m))

def eligible_students(m,offering,d):
    statuses=['Graduated'] if d['kind']=='exit' else ['Active']
    students=Student.objects.filter(institution=m.institution,status__in=statuses,portal_user__is_active=True)
    if offering:
        students=students.filter(pk__in=CourseEnrollment.objects.filter(offering=offering).values('student_id'))
    total_sessions=LectureSession.objects.filter(offering=offering,ends__lte=timezone.now()).count() if offering else 0
    result=[]
    for s in students:
        if d['min_attendance']:
            attendance=SessionAttendance.objects.filter(enrollment__student=s,enrollment__offering=offering,session__offering=offering,session__ends__lte=timezone.now())
            if not total_sessions or attendance.count()!=total_sessions or attendance.filter(present=True).count()*100<d['min_attendance']*total_sessions: continue
        if d['min_fee_paid']:
            fees=FeeAccount.objects.filter(student=s)
            assessed=fees.aggregate(v=Sum('assessed'))['v'] or Decimal(0)
            paid=FeeReceipt.objects.filter(account__in=fees).aggregate(v=Sum('amount'))['v'] or Decimal(0)
            if assessed<=0 or paid*100<assessed*d['min_fee_paid']: continue
        result.append(s)
    return result

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,INTERNAL)
    manager=m.role=='admin'
    now=timezone.now()
    notices=CampusNotice.objects.filter(institution=m.institution) if manager else visible_notices(m)
    acknowledged=set(NoticeAcknowledgment.objects.filter(membership=m,notice__institution=m.institution).values_list('notice_id',flat=True))
    data={'notices':[{**r,'acknowledged':r['id'] in acknowledged} for r in notices.order_by('-created_at').values('id','title','body','kind','audience','starts','ends','link','withdrawn','created_at')]}
    surveys=FeedbackSurvey.objects.filter(institution=m.institution)
    if m.role in ('admin','principal'):
        data['surveys']=[]
        for s in surveys.order_by('-pk'):
            scores=list(s.responses.values_list('scores',flat=True))
            count=len(scores)
            # Do not report individual responses or small-group scores.
            averages=[round(sum(row[k] for row in scores)/count,2) for k in range(len(s.questions))] if count>=3 and now>=s.closes else None
            data['surveys'].append({'id':s.pk,'title':s.title,'kind':s.kind,'scale':s.scale,'questions':s.questions,'opens':s.opens,'closes':s.closes,'cancelled':s.cancelled,'offering':s.offering.course.code+' · '+s.offering.faculty.user.username if s.offering_id else 'Institution','invited':s.invites.count(),'submitted':count,'averages':averages})
        if manager:
            data['offerings']=list(offerings(m).values('id','course__code','batch','faculty__user__username'))
            data['members']=list(Membership.objects.filter(institution=m.institution,role__in=INTERNAL,user__is_active=True).values('id','user__username','role'))
            data['roles']=INTERNAL
    elif m.role in ('student','alumni'):
        invites=FeedbackInvite.objects.filter(survey__in=surveys,student__institution=m.institution,student__portal_user=m.user)
        data['surveys']=list(invites.order_by('-survey_id').values('survey_id','survey__title','survey__kind','survey__scale','survey__questions','survey__opens','survey__closes','survey__cancelled','submitted_at'))
    else:
        data['surveys']=[]
    response=Response(data); response['Cache-Control']='private, no-store'
    return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,INTERNAL)
    schemas={'notice':NoticeInput,'withdraw':Ref,'ack':Ref,'survey':SurveyInput,'cancel':Ref,'answer':AnswerInput}
    if action not in schemas: raise NotFound()
    if action in ('notice','withdraw','survey','cancel') and m.role!='admin': raise PermissionDenied()
    if action=='answer' and m.role not in ('student','alumni'): raise PermissionDenied()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='notice':
            recipient=get(Membership.objects.filter(institution=m.institution,role__in=INTERNAL,user__is_active=True),d.pop('recipient')) if d['recipient'] else None
            d.pop('recipient',None)
            row=CampusNotice.objects.create(institution=m.institution,recipient=recipient,author=m.user,**d)
        elif action=='withdraw':
            row=get(CampusNotice.objects.filter(institution=m.institution),d['id'])
            if row.withdrawn: raise ValidationError('Already withdrawn.')
            row.withdrawn=True;row.save(update_fields=['withdrawn'])
        elif action=='ack':
            notice=get(visible_notices(m),d['id'])
            row,created=NoticeAcknowledgment.objects.get_or_create(notice=notice,membership=m)
            if not created: return Response({'id':row.pk,'duplicate':True})
        elif action=='survey':
            oid=d.pop('offering')
            offering=get(offerings(m),oid) if oid else None
            students=eligible_students(m,offering,d)
            if not students: raise ValidationError('No eligible students for this cohort.')
            row=FeedbackSurvey.objects.create(institution=m.institution,offering=offering,created_by=m.user,**d)
            FeedbackInvite.objects.bulk_create([FeedbackInvite(survey=row,student=s) for s in students])
        elif action=='cancel':
            row=get(FeedbackSurvey.objects.filter(institution=m.institution),d['id'])
            if row.cancelled: raise ValidationError('Already cancelled.')
            row.cancelled=True;row.save(update_fields=['cancelled'])
        else:
            now=timezone.now()
            invite=FeedbackInvite.objects.select_for_update().filter(survey_id=d['id'],survey__institution=m.institution,student__institution=m.institution,student__portal_user=m.user).first()
            if not invite: raise NotFound()
            s=invite.survey
            if s.cancelled or not(s.opens<=now<s.closes) or invite.submitted_at: raise ValidationError('Feedback unavailable or already submitted.')
            maximum=5 if s.scale=='grade' else 100
            if len(d['scores'])!=len(s.questions) or any(v>maximum for v in d['scores']): raise ValidationError('Provide one valid score per question.')
            row=FeedbackResponse.objects.create(survey=s,scores=d['scores'])
            invite.submitted_at=now;invite.save(update_fields=['submitted_at'])
            # Do not log an answer ID against a student actor. Completion timestamps
            # still permit correlation by a privileged database operator.
            log(m,'feedback.complete',s)
            return Response({'submitted':True},status=201)
        log(m,'communication.'+action,row)
    return Response({'id':row.pk},status=201)
