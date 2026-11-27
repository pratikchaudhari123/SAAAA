"""Additive institution-scoped capabilities. Existing legacy module role checks stay intact."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Membership, InstitutionalRole, InstitutionalRoleGrant
from .academic_engine import member, get, parse, log

CAPABILITIES={
 'document.issue':'Review and issue student documents',
 'document.finance':'Confirm finance clearance',
 'document.hostel':'Confirm hostel clearance',
 'document.academic':'Confirm academic clearance',
 'document.library':'Confirm library clearance',
 'document.report':'View institution document register',
}
STAFF=['admin','principal','admissions','faculty','finance','warden','coe','tpo','tpo_assistant']
DEFAULTS={'admin':set(CAPABILITIES),'admissions':{'document.issue','document.report'},'principal':{'document.report'},'finance':{'document.finance'},'warden':{'document.hostel'},'coe':{'document.academic'}}

def inherited(role):
    result=set();seen=set();institution=role.institution_id
    while role:
        if role.pk in seen or role.institution_id!=institution: raise ValidationError('Invalid role hierarchy.')
        seen.add(role.pk);result.update(k for k in role.permissions if k in CAPABILITIES);role=role.parent
    return result

def effective(m):
    result=set(DEFAULTS.get(m.role,set()))
    if m.role not in STAFF: return result
    now=timezone.now()
    grants=InstitutionalRoleGrant.objects.filter(membership=m,role__institution=m.institution,revoked_at__isnull=True,starts__lte=now).filter(Q(ends__isnull=True)|Q(ends__gt=now)).select_related('role')
    for grant in grants: result.update(inherited(grant.role))
    return result

def require(m,cap):
    if cap not in effective(m): raise PermissionDenied('Required institutional permission is not assigned.')

class RoleInput(serializers.Serializer):
    name=serializers.CharField(max_length=100)
    permissions=serializers.ListField(child=serializers.ChoiceField(choices=list(CAPABILITIES)),max_length=len(CAPABILITIES),default=list)
    parent=serializers.IntegerField(min_value=1,required=False,allow_null=True,default=None)
    clone=serializers.IntegerField(min_value=1,required=False,allow_null=True,default=None)
class GrantInput(serializers.Serializer):
    role=serializers.IntegerField(min_value=1)
    membership=serializers.IntegerField(min_value=1)
    starts=serializers.DateTimeField()
    ends=serializers.DateTimeField(required=False,allow_null=True,default=None)
    reason=serializers.CharField(max_length=300)
class Ref(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin'])
    roles=InstitutionalRole.objects.filter(institution=m.institution)
    data={'capabilities':CAPABILITIES,'roles':[{'id':r.pk,'name':r.name,'parent_id':r.parent_id,'permissions':r.permissions,'effective':sorted(inherited(r))} for r in roles.order_by('name')],
          'members':list(Membership.objects.filter(institution=m.institution,role__in=STAFF,user__is_active=True).values('id','user__username','role')),
          'grants':list(InstitutionalRoleGrant.objects.filter(role__in=roles,membership__institution=m.institution).order_by('-pk').values('id','role__name','membership__user__username','starts','ends','revoked_at','reason'))}
    response=Response(data);response['Cache-Control']='private, no-store';return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin'])
    schemas={'role':RoleInput,'grant':GrantInput,'revoke':Ref}
    if action not in schemas: raise NotFound()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        roles=InstitutionalRole.objects.filter(institution=m.institution)
        if action=='role':
            if roles.filter(name__iexact=d['name']).exists(): raise ValidationError('Role name already exists.')
            parent=get(roles,d['parent']) if d['parent'] else None
            clone=get(roles,d['clone']) if d['clone'] else None
            perms=set(d['permissions'])
            if clone: perms.update(inherited(clone))
            if parent: inherited(parent)
            row=InstitutionalRole.objects.create(institution=m.institution,name=d['name'],parent=parent,permissions=sorted(perms),created_by=m.user)
        elif action=='grant':
            role=get(roles,d['role'])
            target=get(Membership.objects.filter(institution=m.institution,role__in=STAFF,user__is_active=True),d['membership'])
            if d['ends'] and (d['ends']<=d['starts'] or d['ends']<=timezone.now()): raise ValidationError('Invalid delegation time window.')
            row=InstitutionalRoleGrant.objects.create(role=role,membership=target,starts=d['starts'],ends=d['ends'],reason=d['reason'],granted_by=m.user)
        else:
            row=get(InstitutionalRoleGrant.objects.filter(role__in=roles,membership__institution=m.institution),d['id'])
            if row.revoked_at: raise ValidationError('Grant already revoked.')
            row.revoked_at=timezone.now();row.save(update_fields=['revoked_at'])
        log(m,'permission.'+action,row)
    return Response({'id':row.pk},status=201)
