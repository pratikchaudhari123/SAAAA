"""Graduation certification and alumni pilot; no automatic degree eligibility inference."""
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Student, Membership, AlumniRecord, AlumniOpportunity, AlumniSettings
from .academic_engine import member, parse, get, log

ROLES=('admin','principal','tpo','tpo_assistant','alumni','student')
class Graduation(serializers.Serializer):
    student_id=serializers.CharField(max_length=50)
    graduation_day=serializers.DateField()
    approval_reference=serializers.CharField(max_length=100)
    confirmed=serializers.BooleanField()
class Profile(serializers.Serializer):
    occupation=serializers.ChoiceField(choices=['unknown','employee','entrepreneur','other'])
    employer=serializers.CharField(max_length=150,allow_blank=True)
    location=serializers.CharField(max_length=150,allow_blank=True)
class Opportunity(serializers.Serializer):
    kind=serializers.ChoiceField(choices=['recruitment','training','mentoring'])
    title=serializers.CharField(max_length=150)
    description=serializers.CharField(max_length=1000)
    contact_url=serializers.URLField(allow_blank=True,required=False,default='')
    def validate_contact_url(self,v):
        if v and not v.startswith('https://'): raise serializers.ValidationError('Use an HTTPS link.')
        return v
class Review(serializers.Serializer):
    opportunity=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['approved','rejected'])
class SettingsInput(serializers.Serializer):
    donation_url=serializers.URLField(allow_blank=True)
    def validate_donation_url(self,v):
        if v and not v.startswith('https://'): raise serializers.ValidationError('Use an approved HTTPS donation page.')
        return v

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,ROLES)
    records=AlumniRecord.objects.filter(student__institution=m.institution)
    opportunities=AlumniOpportunity.objects.filter(alumni__in=records)
    manager=m.role in ('admin','principal','tpo','tpo_assistant')
    own=records.filter(student__portal_user=m.user)
    data={'records':list((records if manager else own).order_by('-graduation_day').values('id','student__student_id','student__name','program_snapshot','graduation_day','occupation','employer','location')),
          'opportunities':list((opportunities if manager else opportunities.filter(status='approved')|opportunities.filter(alumni__in=own)).order_by('-created_at').values('id','kind','title','description','contact_url','status')),
          'donation_url':AlumniSettings.objects.filter(institution=m.institution).values_list('donation_url',flat=True).first() or ''}
    if m.role=='principal':
        data['candidates']=list(Student.objects.filter(institution=m.institution,status='Active').order_by('student_id').values('student_id','name','program','year'))
    response=Response(data); response['Cache-Control']='private, no-store'
    return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,ROLES)
    schemas={'graduate':Graduation,'profile':Profile,'opportunity':Opportunity,'review':Review,'settings':SettingsInput}
    roles={'graduate':('principal',),'profile':('alumni',),'opportunity':('alumni',),'review':('admin','tpo'),'settings':('admin',)}
    if action not in schemas: raise NotFound()
    if m.role not in roles[action]: raise PermissionDenied()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            records=AlumniRecord.objects.filter(student__institution=m.institution)
            if action=='graduate':
                if not d['confirmed'] or d['graduation_day']>timezone.localdate(): raise ValidationError('Confirm an official completed graduation and a non-future date.')
                s=Student.objects.select_for_update().filter(institution=m.institution,student_id=d['student_id'],status='Active').first()
                if not s: raise ValidationError('Select an active student not already graduated.')
                # The authorized principal certifies the official result; this pilot does not infer degree eligibility from individual marks.
                if s.portal_user_id:
                    account=Membership.objects.select_for_update().filter(institution=m.institution,user_id=s.portal_user_id,role='student').first()
                    if not account: raise ValidationError('Student account role must be reconciled first.')
                    account.role='alumni'; account.save(update_fields=['role'])
                row=AlumniRecord.objects.create(student=s,graduation_day=d['graduation_day'],approval_reference=d['approval_reference'],approved_by=m.user,program_snapshot=s.program)
                s.status='Graduated'; s.save(update_fields=['status'])
            elif action=='profile':
                row=records.filter(student__portal_user=m.user).first()
                if not row: raise PermissionDenied()
                for k,v in d.items(): setattr(row,k,v)
                row.save(update_fields=[*d.keys(),'updated_at'])
            elif action=='opportunity':
                own=records.filter(student__portal_user=m.user).first()
                if not own: raise PermissionDenied()
                row=AlumniOpportunity.objects.create(alumni=own,**d)
            elif action=='review':
                row=get(AlumniOpportunity.objects.filter(alumni__in=records),d['opportunity'])
                if row.status!='pending': raise ValidationError('Already reviewed.')
                row.status=d['decision']; row.save(update_fields=['status'])
            else:
                row,_=AlumniSettings.objects.update_or_create(institution=m.institution,defaults=d)
            log(m,'alumni.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid alumni record.')
    return Response({'id':row.pk},status=201)
