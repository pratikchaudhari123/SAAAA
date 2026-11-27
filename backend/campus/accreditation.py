"""Source-derived institutional statistics, not official ranking scores."""
from django.db import transaction
from django.db.models import Count,F,Sum,Q
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied,NotFound,ValidationError
from rest_framework.response import Response
from .models import Institution,AcademicPeriod,Student,Employee,CourseExam,ExamApplication,ExamQuestion,QuestionScore,RecruitmentApplication,AccreditationEvidence,CourseOffering,CourseEnrollment,SessionAttendance
from .academic_engine import member,get,parse,log,offerings
class Evidence(serializers.Serializer):
    period=serializers.IntegerField(min_value=1)
    framework=serializers.ChoiceField(choices=['NBA','NAAC','NIRF'])
    criterion=serializers.CharField(max_length=100)
    title=serializers.CharField(max_length=150)
    description=serializers.CharField(max_length=6000)
    url=serializers.URLField(required=False,allow_blank=True,default='')
    def validate_url(self,v):
        if v and not v.startswith('https://'):raise serializers.ValidationError('HTTPS links only.')
        return v
class Review(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    confirmed=serializers.BooleanField()
def periods(m):return AcademicPeriod.objects.filter(institution=m.institution)
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','principal','coe'])
    ps=periods(m)
    selected=request.query_params.get('period')
    if selected:
        if not selected.isdigit() or len(selected)>18:raise ValidationError('Invalid period.')
        p=get(ps,int(selected))
    else:p=ps.order_by('-starts','-pk').first()
    result={'periods':list(ps.values('id','code','starts','ends')),'period':p.pk if p else None,'current_students':list(Student.objects.filter(institution=m.institution).values('program','status').annotate(count=Count('id')).order_by('program','status')),'current_employees':list(Employee.objects.filter(institution=m.institution,active=True).values('department__code','category').annotate(count=Count('id')).order_by('department__code','category')),'results':[],'questions':[],'placements':[],'attendance':[],'evidence':[]}
    if p:
        os=offerings(m).filter(period=p)
        apps=ExamApplication.objects.filter(exam__offering__in=os,exam__status='published',enrollment__student__institution=m.institution,marks__isnull=False)
        result['results']=list(apps.values('exam__offering__course__program__name','exam__offering__course__code').annotate(attempts=Count('id'),passed=Count('id',filter=Q(marks__gte=F('exam__passing')))).order_by('exam__offering__course__code'))
        scores=QuestionScore.objects.filter(evaluation__application__in=apps,evaluation__status='approved')
        result['questions']=list(scores.values('question__exam__title','question__code','question__maximum').annotate(graded=Count('id'),total_marks=Sum('marks')).order_by('question__exam__title','question__code'))
        result['placements']=list(RecruitmentApplication.objects.filter(student__institution=m.institution,drive__company__institution=m.institution,drive__drive_day__range=(p.starts,p.ends),status='selected').values('student__program','drive__kind').annotate(unique_students=Count('student_id',distinct=True),selections=Count('id')).order_by('student__program','drive__kind'))
        result['attendance']=list(SessionAttendance.objects.filter(session__offering__in=os,enrollment__student__institution=m.institution,session__offering=F('enrollment__offering')).values('session__offering__course__code').annotate(recorded=Count('id'),present=Count('id',filter=Q(present=True))).order_by('session__offering__course__code'))
        result['evidence']=list(AccreditationEvidence.objects.filter(period=p).order_by('framework','criterion','pk').values('id','framework','criterion','title','description','url','status','created_at'))
    response=Response(result);response['Cache-Control']='private, no-store';return response
@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','principal','coe'])
    schemas={'evidence':Evidence,'review':Review}
    if action not in schemas:raise NotFound()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='evidence':
            if m.role not in ('admin','coe'):raise PermissionDenied()
            p=get(periods(m),d.pop('period'))
            row=AccreditationEvidence.objects.create(period=p,created_by=m.user,**d)
        else:
            if m.role!='principal':raise PermissionDenied()
            row=get(AccreditationEvidence.objects.filter(period__in=periods(m)),d['id'])
            if not d['confirmed'] or row.status!='draft':raise ValidationError('Confirm a pending evidence record.')
            row.status='reviewed';row.reviewed_by=m.user;row.save(update_fields=['status','reviewed_by'])
        log(m,'accreditation.'+action,row)
    return Response({'id':row.pk},status=201)
