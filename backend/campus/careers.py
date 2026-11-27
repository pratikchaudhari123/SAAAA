"""Tenant-scoped recruitment pilot; eligibility is program/year based."""
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Student, AcademicProgram, RecruitmentCompany, CareerProfile, RecruitmentDrive, RecruitmentApplication
from .academic_engine import member, get, parse, log

MANAGERS=('admin','tpo','tpo_assistant')
ROLES=(*MANAGERS,'principal','student','company')
class CompanyInput(serializers.Serializer):
    name=serializers.CharField(max_length=150)
    contact_email=serializers.EmailField()
    description=serializers.CharField(max_length=500,allow_blank=True,required=False,default='')
class ReviewInput(serializers.Serializer):
    company=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['approved','rejected'])
    note=serializers.CharField(max_length=300,allow_blank=True,required=False,default='')
class ProfileInput(serializers.Serializer):
    skills=serializers.CharField(max_length=500)
    summary=serializers.CharField(max_length=1000)
class DriveInput(serializers.Serializer):
    company=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    kind=serializers.ChoiceField(choices=['job','internship','training'])
    program=serializers.CharField(max_length=150,allow_blank=True,required=False,default='')
    min_year=serializers.IntegerField(min_value=1,max_value=8)
    max_year=serializers.IntegerField(min_value=1,max_value=8)
    deadline=serializers.DateField()
    drive_day=serializers.DateField()
    instructions=serializers.CharField(max_length=1000)
class DriveRef(serializers.Serializer):
    drive=serializers.IntegerField(min_value=1)
class ApplyInput(DriveRef):
    consent=serializers.BooleanField()
class DecisionInput(serializers.Serializer):
    application=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['shortlisted','selected','rejected','withdrawn'])

def eligible_students(drive):
    qs=Student.objects.filter(institution=drive.company.institution,status='Active',year__gte=drive.min_year,year__lte=drive.max_year)
    return qs.filter(program=drive.program) if drive.program else qs

def open_for(drive):
    return drive.status=='open' and drive.company.status=='approved' and drive.deadline>=timezone.localdate()

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,ROLES)
    management=m.role in (*MANAGERS,'principal')
    companies=RecruitmentCompany.objects.filter(institution=m.institution,membership__institution=m.institution)
    drives=RecruitmentDrive.objects.filter(company__in=companies)
    apps=RecruitmentApplication.objects.filter(drive__in=drives,student__institution=m.institution)
    data={}
    if m.role=='company':
        companies=companies.filter(membership=m)
        drives=drives.filter(company__in=companies)
        apps=apps.filter(drive__in=drives,drive__company__status='approved').exclude(status='withdrawn')
    elif m.role=='student':
        s=Student.objects.filter(institution=m.institution,portal_user=m.user,status='Active').first()
        if not s: raise PermissionDenied('Active student profile required.')
        apps=apps.filter(student=s)
        drives=drives.filter(Q(status='open',company__status='approved',deadline__gte=timezone.localdate(),min_year__lte=s.year,max_year__gte=s.year,program__in=['',s.program])|Q(applications__student=s)).distinct()
        companies=companies.filter(drives__in=drives).distinct()
        data['profile']=CareerProfile.objects.filter(student=s).values('skills','summary').first()
    company_fields=['id','name','status']
    if m.role!='student': company_fields+=['contact_email','description','review_note']
    data['companies']=list(companies.order_by('name').values(*company_fields))
    data['drives']=list(drives.order_by('-drive_day','id').values('id','company_id','company__name','title','kind','program','min_year','max_year','deadline','drive_day','instructions','status'))
    fields=['id','drive_id','drive__title','status','applied_at']
    if management or m.role=='company':
        fields+=['student__student_id','student__name','student__program','student__year','skills','summary']
    data['applications']=list(apps.order_by('-applied_at').values(*fields))
    if management:
        data['programs']=sorted(set(AcademicProgram.objects.filter(department__institution=m.institution,active=True).values_list('name',flat=True))|set(Student.objects.filter(institution=m.institution,status='Active').values_list('program',flat=True)))
        data['eligible_counts']=[{'drive':d.pk,'count':eligible_students(d).count()} for d in drives.select_related('company')]
        data['selected_count']=apps.filter(status='selected',drive__kind='job').count()
        data['internship_count']=apps.filter(status='selected',drive__kind='internship').count()
    response=Response(data)
    response['Cache-Control']='private, no-store'
    return response

@api_view(['GET'])
def eligible(request,slug,pk):
    m=member(request,slug,(*MANAGERS,'principal'))
    drive=get(RecruitmentDrive.objects.filter(company__institution=m.institution,company__membership__institution=m.institution),pk)
    return Response(list(eligible_students(drive).order_by('student_id').values('student_id','name','program','year')))

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,ROLES)
    schemas={'company':CompanyInput,'company-review':ReviewInput,'profile':ProfileInput,'drive':DriveInput,'close':DriveRef,'apply':ApplyInput,'decision':DecisionInput}
    roles={'company':('company',),'company-review':('admin','tpo'),'profile':('student',),'drive':MANAGERS,'close':MANAGERS,'apply':('student',),'decision':(*MANAGERS,'student')}
    if action not in schemas: raise NotFound()
    if m.role not in roles[action]: raise PermissionDenied()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            companies=RecruitmentCompany.objects.filter(institution=m.institution,membership__institution=m.institution)
            drives=RecruitmentDrive.objects.filter(company__in=companies)
            apps=RecruitmentApplication.objects.filter(drive__in=drives,student__institution=m.institution)
            student=Student.objects.filter(institution=m.institution,portal_user=m.user,status='Active').first()
            if action=='company':
                row=RecruitmentCompany.objects.create(institution=m.institution,membership=m,**d)
            elif action=='company-review':
                row=get(companies,d['company'])
                if row.status!='pending': raise ValidationError('Company review is already completed.')
                if d['decision']=='rejected' and not d['note'].strip(): raise ValidationError('Provide rejection reason.')
                row.status=d['decision']; row.review_note=d['note']
                row.save(update_fields=['status','review_note'])
            elif action=='profile':
                if not student: raise PermissionDenied('Active student profile required.')
                row,_=CareerProfile.objects.update_or_create(student=student,defaults=d)
            elif action=='drive':
                company=get(companies.filter(status='approved'),d.pop('company'))
                if d['min_year']>d['max_year'] or d['deadline']<timezone.localdate() or d['drive_day']<d['deadline']: raise ValidationError('Invalid year range or recruitment dates.')
                if d['program'] and not (AcademicProgram.objects.filter(department__institution=m.institution,active=True,name=d['program']).exists() or Student.objects.filter(institution=m.institution,status='Active',program=d['program']).exists()): raise ValidationError('Program not available in this institution.')
                row=RecruitmentDrive.objects.create(company=company,**d)
            elif action=='close':
                row=get(drives,d['drive'])
                if row.status!='open': raise ValidationError('Drive already closed.')
                row.status='closed'; row.save(update_fields=['status'])
            elif action=='apply':
                if not student or not d['consent']: raise ValidationError('Active student and consent to share the application are required.')
                drive=get(drives,d['drive'])
                if not open_for(drive) or not eligible_students(drive).filter(pk=student.pk).exists(): raise ValidationError('Drive closed or student not eligible.')
                profile=CareerProfile.objects.filter(student=student).first()
                if not profile: raise ValidationError('Complete your career profile first.')
                row=RecruitmentApplication.objects.create(drive=drive,student=student,skills=profile.skills,summary=profile.summary)
            else:
                row=get(apps.filter(student=student) if m.role=='student' and student else apps.none() if m.role=='student' else apps,d['application'])
                decision=d['decision']
                if m.role=='student':
                    if decision!='withdrawn': raise PermissionDenied()
                    if row.status not in ('submitted','shortlisted'): raise ValidationError('Application cannot be withdrawn at this stage.')
                else:
                    if decision=='withdrawn': raise PermissionDenied()
                    if row.drive.status!='closed': raise ValidationError('Close applications before selection decisions.')
                    allowed={'submitted':('shortlisted','rejected'),'shortlisted':('selected','rejected')}
                    if decision not in allowed.get(row.status,()): raise ValidationError('Invalid recruitment transition.')
                row.status=decision; row.save(update_fields=['status'])
            log(m,'career.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid recruitment record.')
    return Response({'id':row.pk},status=201)
