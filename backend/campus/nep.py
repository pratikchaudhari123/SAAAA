"""Internal credit-recognition register; no ABC submission or automatic awards."""
from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError,PermissionDenied,NotFound
from rest_framework.response import Response
from .models import Institution,Student,AcademicCourse,CreditRecognition
from .academic_engine import member,get,parse,log
class Apply(serializers.Serializer):
    course=serializers.IntegerField(min_value=1)
    source_institution=serializers.CharField(max_length=200)
    source_reference=serializers.CharField(max_length=100)
    evidence_url=serializers.URLField(required=False,allow_blank=True,default='')
    credits=serializers.IntegerField(min_value=1,max_value=100)
    def validate_evidence_url(self,v):
        if v and not v.startswith('https://'):raise serializers.ValidationError('HTTPS references only.')
        return v
class Review(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['approved','rejected'])
    note=serializers.CharField(max_length=500)
def students(m):
    q=Student.objects.filter(institution=m.institution)
    return q.filter(portal_user=m.user,status='Active') if m.role=='student' else q
def courses(m):return AcademicCourse.objects.filter(program__department__institution=m.institution,active=True,program__active=True,program__department__active=True)
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','principal','coe','student'])
    ss=students(m);cs=courses(m)
    if m.role=='student':cs=cs.filter(program__name__in=ss.values('program'))
    q=CreditRecognition.objects.filter(student__in=ss,course__program__department__institution=m.institution)
    r=Response({'courses':list(cs.values('id','code','name','credits')),'records':list(q.order_by('-pk').values('id','student__student_id','student__name','course__code','source_institution','source_reference','evidence_url','credits','status','review_note')),'approved_credits':q.filter(status='approved').aggregate(v=Sum('credits'))['v'] or 0})
    r['Cache-Control']='private, no-store';return r
@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['student','principal'])
    if action not in ('apply','review'):raise NotFound()
    d=parse(Apply if action=='apply' else Review,request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='apply':
            if m.role!='student':raise PermissionDenied()
            s=students(m).first()
            if not s:raise PermissionDenied()
            course=get(courses(m).filter(program__name=s.program),d.pop('course'))
            if d['credits']>course.credits:raise ValidationError('Requested credits exceed mapped course credits.')
            if CreditRecognition.objects.filter(student=s,source_reference=d['source_reference']).exists():raise ValidationError('Source reference already registered.')
            row=CreditRecognition.objects.create(student=s,course=course,**d)
        else:
            if m.role!='principal':raise PermissionDenied()
            row=get(CreditRecognition.objects.filter(student__institution=m.institution,course__program__department__institution=m.institution),d['id'])
            if row.status!='pending':raise ValidationError('Already reviewed.')
            if d['decision']=='approved':
                if row.student.status!='Active' or not row.course.active or row.student.program!=row.course.program.name:raise ValidationError('Student or course mapping changed.')
                total=CreditRecognition.objects.filter(student=row.student,course=row.course,status='approved').aggregate(v=Sum('credits'))['v'] or 0
                if total+row.credits>row.course.credits:raise ValidationError('Approved credits would exceed mapped course maximum.')
            row.status=d['decision'];row.review_note=d['note'];row.reviewed_by=m.user;row.save(update_fields=['status','review_note','reviewed_by'])
        log(m,'nep.'+action,row)
    return Response({'id':row.pk},status=201)
