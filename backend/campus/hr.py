"""Employee register, self-service and authorized device-event projection."""
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Membership, Department, Employee, EmployeeDeviceIdentity, EmployeePunch, EmployeeLeave, IntegrationSource
from .academic_engine import member, get, parse, log

STAFF=['admin','principal','admissions','faculty','finance','warden','coe']

class EmployeeInput(serializers.Serializer):
    code=serializers.CharField(max_length=50)
    name=serializers.CharField(max_length=150)
    designation=serializers.CharField(max_length=100)
    category=serializers.ChoiceField(choices=['teaching','non_teaching','contract'])
    department=serializers.IntegerField(min_value=1)
    membership=serializers.IntegerField(min_value=1,required=False,allow_null=True,default=None)
    joined_on=serializers.DateField()
class MapInput(serializers.Serializer):
    employee=serializers.IntegerField(min_value=1)
    source=serializers.IntegerField(min_value=1)
    subject_ref=serializers.RegexField(regex=r'^[A-Za-z0-9_.:-]+$',max_length=100)
class LeaveInput(serializers.Serializer):
    category=serializers.CharField(max_length=40)
    starts=serializers.DateField()
    ends=serializers.DateField()
    reason=serializers.CharField(max_length=300)
class ReviewInput(serializers.Serializer):
    leave=serializers.IntegerField(min_value=1)
    decision=serializers.ChoiceField(choices=['approved','rejected','withdrawn'])
    note=serializers.CharField(max_length=300,allow_blank=True,required=False,default='')

def project_employee_event(event):
    """Only new, directional events after explicit identity enrollment are projected."""
    if event.source.purpose!='employee' or event.event_type not in ('in','out'):
        return False
    mapping=EmployeeDeviceIdentity.objects.filter(source=event.source,subject_ref=event.subject_ref,employee__institution=event.source.institution,employee__active=True,effective_from__lte=event.occurred_at).first()
    if not mapping or timezone.localdate(event.occurred_at)<mapping.employee.joined_on:
        return False
    EmployeePunch.objects.get_or_create(event=event,defaults={'employee':mapping.employee})
    return True

def employee_scope(m):
    return Employee.objects.filter(institution=m.institution,department__institution=m.institution)

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,STAFF)
    management=m.role in ('admin','principal')
    employees=employee_scope(m)
    own=employees.filter(membership=m,active=True)
    visible=employees if management else own
    leaves=EmployeeLeave.objects.filter(employee__in=visible).order_by('-created_at')[:200]
    punches=EmployeePunch.objects.filter(employee__in=visible,event__source__institution=m.institution).order_by('-event__occurred_at')[:300]
    data={'employees':list(visible.order_by('code').values('id','code','name','designation','category','department__name','joined_on','active')),
        'own_employee':own.values('id','code','name').first(),
        'leaves':list(leaves.values('id','employee__code','employee__name','employee_id','category','starts','ends','reason','status','review_note')),
        'punches':list(punches.values('employee__code','employee__name','event__source__name','event__event_type','event__occurred_at'))}
    if m.role=='admin':
        data.update({'departments':list(Department.objects.filter(institution=m.institution,active=True).values('id','name','code')),
            'accounts':list(Membership.objects.filter(institution=m.institution,role__in=STAFF,user__is_active=True,employee__isnull=True).values('id','user__username')),
            'sources':list(IntegrationSource.objects.filter(institution=m.institution,purpose='employee',active=True).values('id','name')),
            'mappings':list(EmployeeDeviceIdentity.objects.filter(source__institution=m.institution,employee__institution=m.institution).values('source__name','employee__code','subject_ref','effective_from'))})
    return Response(data)

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,STAFF)
    schemas={'employee':EmployeeInput,'map':MapInput,'leave':LeaveInput,'review':ReviewInput}
    if action not in schemas: raise NotFound()
    if action in ('employee','map') and m.role!='admin': raise PermissionDenied()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            employees=employee_scope(m)
            own=employees.filter(membership=m,active=True).first()
            if action=='employee':
                dep=get(Department.objects.filter(institution=m.institution,active=True),d.pop('department'))
                mid=d.pop('membership')
                account=get(Membership.objects.filter(institution=m.institution,role__in=STAFF,user__is_active=True),mid) if mid else None
                if d['joined_on']>timezone.localdate(): raise ValidationError('Joining date must not be in the future.')
                row=Employee.objects.create(institution=m.institution,department=dep,membership=account,**d)
            elif action=='map':
                employee=get(employees.filter(active=True),d['employee'])
                source=get(IntegrationSource.objects.filter(institution=m.institution,purpose='employee',active=True),d['source'])
                row=EmployeeDeviceIdentity.objects.create(employee=employee,source=source,subject_ref=d['subject_ref'])
            elif action=='leave':
                if not own: raise PermissionDenied('An active employee profile is required.')
                if d['starts']<timezone.localdate() or d['ends']<d['starts'] or (d['ends']-d['starts']).days>365:
                    raise ValidationError('Choose valid future or current leave dates, up to 366 calendar days.')
                if EmployeeLeave.objects.filter(employee=own,status__in=['pending','approved'],starts__lte=d['ends'],ends__gte=d['starts']).exists():
                    raise ValidationError('Overlapping pending or approved leave.')
                row=EmployeeLeave.objects.create(employee=own,**d)
            else:
                row=get(EmployeeLeave.objects.filter(employee__in=employees),d['leave'])
                if d['decision']=='withdrawn':
                    if not own or row.employee_id!=own.pk: raise PermissionDenied()
                elif m.role!='principal' or row.employee.membership_id==m.pk:
                    raise PermissionDenied('Only the principal may review another employee request.')
                if row.status!='pending': raise ValidationError('Only pending leave can be changed.')
                if d['decision']=='rejected' and not d['note'].strip(): raise ValidationError('Provide a rejection reason.')
                row.status=d['decision']
                row.reviewed_by=m.user
                row.reviewed_at=timezone.now()
                row.review_note=d['note']
                row.save(update_fields=['status','reviewed_by','reviewed_at','review_note'])
            log(m,'hr.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate employee, account link or device mapping.')
    return Response({'id':row.pk},status=201)
