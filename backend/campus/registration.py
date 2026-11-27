"""Invited applicant self-registration; official qualification/document verification by admissions."""
import hashlib
from decimal import Decimal
from uuid import uuid4
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Membership, AcademicProgram, RegistrationRule, AdmissionApplication, AdmissionDocument, Student
from .academic_engine import member, get, parse, log
from .scans import normalize

KINDS=['photo','identity','ssc','hsc','degree','qualification']
ROLES=['admin','admissions','applicant']
class RuleInput(serializers.Serializer):
    program=serializers.IntegerField(min_value=1)
    code=serializers.RegexField(regex=r'^[A-Za-z0-9_-]+$',max_length=30)
    opens=serializers.DateField()
    closes=serializers.DateField()
    qualification=serializers.CharField(max_length=100)
    minimum_percent=serializers.DecimalField(max_digits=5,decimal_places=2,min_value=Decimal(0),max_value=Decimal(100))
    seats=serializers.IntegerField(min_value=1,max_value=10000)
    estimated_fee=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=Decimal(0))
    required_documents=serializers.ListField(child=serializers.ChoiceField(choices=KINDS),max_length=6)
    def validate(self,d):
        if d['closes']<d['opens'] or d['closes']<timezone.localdate(): raise serializers.ValidationError('Invalid admission dates.')
        if len(set(d['required_documents']))!=len(d['required_documents']): raise serializers.ValidationError('Duplicate document type.')
        return d
class Draft(serializers.Serializer):
    rule=serializers.IntegerField(min_value=1)
    name=serializers.CharField(max_length=200,allow_blank=True,default='')
    email=serializers.EmailField(allow_blank=True,default='')
    qualification=serializers.CharField(max_length=100,allow_blank=True,default='')
    percent=serializers.DecimalField(max_digits=5,decimal_places=2,min_value=Decimal(0),max_value=Decimal(100),allow_null=True,default=None)
class Document(serializers.Serializer):
    kind=serializers.ChoiceField(choices=KINDS)
    image=serializers.CharField(max_length=2000000)
class Submit(serializers.Serializer):
    confirmed=serializers.BooleanField()
class Review(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['approved','returned','rejected'])
    note=serializers.CharField(max_length=500)
    verified=serializers.BooleanField(default=False)

def rules(m):
    return RegistrationRule.objects.filter(institution=m.institution,program__department__institution=m.institution)
def available(m):
    today=timezone.localdate()
    return rules(m).filter(opens__lte=today,closes__gte=today,program__active=True,program__department__active=True)
def apps(m):
    q=AdmissionApplication.objects.filter(membership__institution=m.institution,rule__in=rules(m))
    return q.filter(membership=m) if m.role=='applicant' else q
def own(m):
    row=apps(m).first()
    if row is None: raise ValidationError('Save a draft first.')
    return row
def mutable(row):
    if row.status not in ('draft','returned'): raise ValidationError('Application is locked.')
def complete(row):
    if not row.name or not row.email or row.percent is None or row.qualification.casefold()!=row.rule.qualification.casefold() or row.percent<row.rule.minimum_percent:
        raise ValidationError('Complete the profile and satisfy the configured qualification and percentage criteria.')
    if not set(row.rule.required_documents).issubset(set(row.documents.values_list('kind',flat=True))):
        raise ValidationError('Upload every required supporting document.')
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,ROLES)
    selected=apps(m)
    r=rules(m) if m.role!='applicant' else rules(m).filter(pk__in=available(m).values('pk'))|rules(m).filter(pk__in=selected.values('rule_id'))
    data={'rules':list(r.order_by('code').values('id','code','program__name','opens','closes','qualification','minimum_percent','seats','estimated_fee','required_documents')),
        'applications':[],'document_kinds':KINDS}
    for a in selected.select_related('rule','student','membership__user').order_by('-pk'):
        data['applications'].append({'id':a.pk,'rule_id':a.rule_id,'rule_code':a.rule.code,'name':a.name,'email':a.email,'qualification':a.qualification,'percent':a.percent,'status':a.status,'review_note':a.review_note,'student_id':a.student.student_id if a.student_id else None,'username':a.membership.user.username,'documents':list(a.documents.values('id','kind','sha256'))})
    if m.role=='admin':
        data['programs']=list(AcademicProgram.objects.filter(department__institution=m.institution,department__active=True,active=True).values('id','name','code','intake'))
    response=Response(data);response['Cache-Control']='private, no-store'
    return response

@api_view(['GET'])
def document_view(request,slug,pk):
    m=member(request,slug,ROLES)
    row=get(AdmissionDocument.objects.filter(application__in=apps(m)),pk)
    response=HttpResponse(bytes(row.image),content_type='image/jpeg')
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,ROLES)
    schemas={'rule':RuleInput,'draft':Draft,'document':Document,'submit':Submit,'review':Review}
    roles={'rule':['admin'],'draft':['applicant'],'document':['applicant'],'submit':['applicant'],'review':['admin','admissions']}
    if action not in schemas: raise NotFound()
    if m.role not in roles[action]: raise PermissionDenied()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='rule':
            p=get(AcademicProgram.objects.filter(department__institution=m.institution,department__active=True,active=True),d.pop('program'))
            if d['seats']>p.intake or rules(m).filter(code=d['code']).exists(): raise ValidationError('Seat limit exceeds program intake or rule code already exists.')
            row=RegistrationRule.objects.create(institution=m.institution,program=p,**d)
        elif action=='draft':
            rule=get(available(m),d.pop('rule'))
            row=apps(m).first()
            if row:
                mutable(row)
                if row.rule_id!=rule.pk and row.documents.exists(): raise ValidationError('Cannot change program after uploading documents.')
                row.rule=rule
                for k,v in d.items(): setattr(row,k,v)
                row.save()
            else:
                row=AdmissionApplication.objects.create(membership=m,rule=rule,**d)
        elif action=='document':
            a=own(m);mutable(a)
            if not available(m).filter(pk=a.rule_id).exists(): raise ValidationError('Registration window closed.')
            if d['kind'] not in a.rule.required_documents: raise ValidationError('This document type is not required.')
            image,width,height=normalize(d['image'])
            row,_=AdmissionDocument.objects.update_or_create(application=a,kind=d['kind'],defaults={'image':image,'sha256':hashlib.sha256(image).hexdigest()})
        elif action=='submit':
            row=own(m);mutable(row)
            if not d['confirmed'] or not available(m).filter(pk=row.rule_id).exists(): raise ValidationError('Confirm application during open registration.')
            complete(row)
            row.status='submitted';row.save(update_fields=['status','updated_at'])
        else:
            row=get(apps(m),d['id'])
            if row.status!='submitted': raise ValidationError('Only submitted applications can be reviewed.')
            if d['decision']=='approved':
                if not d['verified']: raise ValidationError('Verify qualification, documents and identity before approval.')
                complete(row)
                rule=row.rule
                if not rule.program.active or not rule.program.department.active: raise ValidationError('Program is inactive.')
                if AdmissionApplication.objects.filter(rule=rule,status='approved').count()>=rule.seats: raise ValidationError('Admission window seat limit reached.')
                if Student.objects.filter(institution=m.institution,email__iexact=row.email).exists() or Student.objects.filter(institution=m.institution,portal_user=row.membership.user).exists(): raise ValidationError('Possible duplicate student. Reconcile identity before approving.')
                if row.membership.role!='applicant': raise ValidationError('Applicant account role changed.')
                s=Student.objects.create(institution=m.institution,student_id='ADM-'+uuid4().hex[:16].upper(),name=row.name,email=row.email,program=rule.program.name,year=1,status='Active',portal_user=row.membership.user)
                row.student=s
                row.membership.role='student';row.membership.save(update_fields=['role'])
            row.status=d['decision'];row.review_note=d['note'];row.save()
        log(m,'registration.'+action,row)
    return Response({'id':row.pk},status=201)
