"""Student document request/clearance/issuance pilot; no legal digital signature."""
from decimal import Decimal
from uuid import uuid4
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Student, CertificatePolicy, CertificateRequest, CertificateClearance, FeeAccount, FeeReceipt, HostelBed
from .academic_engine import member, get, parse, log
from .permissions import STAFF, effective, require

UNITS=['finance','hostel','academic','library']
KINDS=['bonafide','character','fee_statement','clearance','student_id']
ROLES=[*STAFF,'student','alumni']
TOKENS=['student_name','student_id','program','year','institution','issue_date','serial','copy_kind','fee_assessed','fee_paid','fee_outstanding']
class PolicyInput(serializers.Serializer):
    code=serializers.RegexField(regex=r'^[A-Za-z0-9_-]+$',max_length=30)
    kind=serializers.ChoiceField(choices=KINDS)
    title=serializers.CharField(max_length=150)
    text=serializers.CharField(max_length=3000)
    allow_duplicate=serializers.BooleanField(default=False)
    clearance_units=serializers.ListField(child=serializers.ChoiceField(choices=UNITS),max_length=4,default=list)
    def validate(self,d):
        import re
        if set(re.findall(r'\{([^{}]+)\}',d['text']))-set(TOKENS): raise serializers.ValidationError('Unknown template token.')
        if len(set(d['clearance_units']))!=len(d['clearance_units']): raise serializers.ValidationError('Duplicate clearance unit.')
        if d['kind']=='clearance' and not d['clearance_units']: raise serializers.ValidationError('Clearance requires at least one unit.')
        return d
class ApplicationInput(serializers.Serializer):
    policy=serializers.IntegerField(min_value=1)
    copy_kind=serializers.ChoiceField(choices=['original','duplicate'])
    reason=serializers.CharField(max_length=300)
class ClearanceInput(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    unit=serializers.ChoiceField(choices=UNITS)
    cleared=serializers.BooleanField()
    note=serializers.CharField(max_length=300)
class ReviewInput(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['issued','rejected','revoked'])
    note=serializers.CharField(max_length=500)
    confirmed=serializers.BooleanField(default=False)

def fee_summary(s):
    accounts=FeeAccount.objects.filter(student=s)
    assessed=accounts.aggregate(v=Sum('assessed'))['v'] or Decimal('0')
    paid=FeeReceipt.objects.filter(account__in=accounts).aggregate(v=Sum('amount'))['v'] or Decimal('0')
    return {'fee_assessed':format(assessed,'.2f'),'fee_paid':format(paid,'.2f'),'fee_outstanding':format(assessed-paid,'.2f')}

def requests(m):
    return CertificateRequest.objects.filter(student__institution=m.institution,policy__institution=m.institution)
def own_student(m):
    return Student.objects.filter(institution=m.institution,portal_user=m.user,status__in=['Active','Graduated']).first()
def permitted_student(m):
    s=own_student(m)
    if not s: raise PermissionDenied('Active or graduated student profile required.')
    return s
def policy_data(p):
    return {'code':p.code,'kind':p.kind,'title':p.title,'text':p.text,'allow_duplicate':p.allow_duplicate,'clearance_units':p.clearance_units}
def serialize(r,full=False):
    data={'id':r.pk,'policy_id':r.policy_id,'title':r.policy_snapshot['title'],'kind':r.policy_snapshot['kind'],'copy_kind':r.copy_kind,'status':r.status,'reason':r.reason,'review_note':r.review_note,'created_at':r.created_at,'required_units':r.policy_snapshot['clearance_units'],'clearances':list(r.clearances.values('unit','cleared','note','updated_at')),'serial':str(r.serial) if r.serial else None,'issued':r.issued_snapshot if r.status=='issued' else None}
    if full: data.update({'student_id':r.student.student_id,'name':r.student.name,'program':r.student.program})
    return data
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,ROLES)
    caps=effective(m);personal=m.role in ('student','alumni')
    qs=requests(m)
    if personal:
        qs=qs.filter(student=permitted_student(m))
    elif not caps: qs=qs.none()
    elif not {'document.issue','document.report'}.intersection(caps):
        # Clearance officers see only pending requests requiring their unit.
        units={k.split('.')[1] for k in caps if k.split('.')[1] in UNITS}
        ids=[r.pk for r in qs.filter(status='pending') if units.intersection(r.policy_snapshot['clearance_units'])]
        qs=qs.filter(pk__in=ids)
    policies=CertificatePolicy.objects.filter(institution=m.institution)
    if personal: policies=policies.filter(active=True)
    if not personal and not caps: policies=policies.none()
    data={'capabilities':sorted(caps),'policies':[{'id':p.pk,**policy_data(p)} for p in policies.order_by('code')],'requests':[serialize(r,not personal) for r in qs.select_related('student').order_by('-pk')],'tokens':TOKENS,'units':UNITS,'kinds':KINDS}
    response=Response(data);response['Cache-Control']='private, no-store';return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,ROLES)
    schemas={'policy':PolicyInput,'apply':ApplicationInput,'clearance':ClearanceInput,'review':ReviewInput}
    if action not in schemas: raise NotFound()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        if action=='policy':
            if m.role!='admin': raise PermissionDenied()
            if CertificatePolicy.objects.filter(institution=m.institution,code=d['code']).exists(): raise ValidationError('Use a new code for a new template version.')
            row=CertificatePolicy.objects.create(institution=m.institution,**d)
        elif action=='apply':
            if m.role not in ('student','alumni'): raise PermissionDenied()
            s=permitted_student(m)
            p=get(CertificatePolicy.objects.filter(institution=m.institution,active=True),d['policy'])
            if p.kind in ('bonafide','student_id') and s.status!='Active': raise ValidationError('This document requires active enrollment.')
            related=requests(m).filter(student=s,policy__kind=p.kind)
            if related.filter(status='pending').exists(): raise ValidationError('A request is already pending for this document type.')
            original=related.filter(copy_kind='original',status='issued').order_by('-pk').first()
            if d['copy_kind']=='original' and original: raise ValidationError('An original already exists; apply for a duplicate.')
            if d['copy_kind']=='duplicate' and (not original or not p.allow_duplicate): raise ValidationError('An issued original and duplicate policy are required.')
            row=CertificateRequest.objects.create(policy=p,student=s,copy_kind=d['copy_kind'],original=original if d['copy_kind']=='duplicate' else None,reason=d['reason'],policy_snapshot=policy_data(p))
        elif action=='clearance':
            require(m,'document.'+d['unit'])
            r=get(requests(m),d['id'])
            if r.status!='pending' or d['unit'] not in r.policy_snapshot['clearance_units']: raise ValidationError('Clearance is not required or request is locked.')
            if d['cleared'] and d['unit']=='finance' and Decimal(fee_summary(r.student)['fee_outstanding'])!=0: raise ValidationError('Recorded fee balance must be reconciled to zero first.')
            if d['cleared'] and d['unit']=='hostel' and r.policy.kind=='clearance' and HostelBed.objects.filter(institution=m.institution,student=r.student).exists(): raise ValidationError('Release allocated hostel bed before final clearance.')
            row,_=CertificateClearance.objects.update_or_create(request=r,unit=d['unit'],defaults={'cleared':d['cleared'],'note':d['note'],'actor':m.user})
        else:
            require(m,'document.issue')
            row=get(requests(m),d['id'])
            decision=d['decision']
            if decision=='revoked':
                if row.status!='issued': raise ValidationError('Only issued documents can be revoked.')
            elif row.status!='pending': raise ValidationError('Only pending requests may be reviewed.')
            if decision=='issued':
                if not d['confirmed']: raise ValidationError('Authorized officer must confirm the document details.')
                units=set(row.policy_snapshot['clearance_units'])
                if units-set(row.clearances.filter(cleared=True).values_list('unit',flat=True)): raise ValidationError('Required clearances incomplete.')
                s=row.student
                if s.status not in ('Active','Graduated') or (row.policy.kind in ('bonafide','student_id') and s.status!='Active'): raise ValidationError('Student status no longer eligible.')
                amounts=fee_summary(s)
                if 'finance' in units and Decimal(amounts['fee_outstanding'])!=0: raise ValidationError('Fee balance changed; reconcile before issue.')
                if 'hostel' in units and row.policy.kind=='clearance' and HostelBed.objects.filter(institution=m.institution,student=s).exists(): raise ValidationError('Hostel allocation changed.')
                if row.copy_kind=='duplicate' and (not row.original_id or row.original.status!='issued'): raise ValidationError('Original no longer valid.')
                row.serial=uuid4();row.issued_at=timezone.now();row.issued_by=m.user
                values={'student_name':s.name,'student_id':s.student_id,'program':s.program,'year':str(s.year),'institution':m.institution.name,'issue_date':str(timezone.localdate()),'serial':str(row.serial),'copy_kind':row.copy_kind,**amounts}
                import re
                text=re.sub(r'\{([^{}]+)\}',lambda match: values.get(match.group(1),match.group(0)),row.policy_snapshot['text'])
                row.issued_snapshot={**values,'title':row.policy_snapshot['title'],'text':text,'approval_reference':d['note'],'original_serial':str(row.original.serial) if row.original_id else None}
            row.status=decision;row.review_note=d['note'];row.save()
        log(m,'document.'+action,row)
    return Response({'id':row.pk},status=201)
