"""Institution-scoped service desk with explicit SLA policy and append-only history."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound,PermissionDenied,ValidationError
from rest_framework.response import Response
from .models import Institution,Membership,SupportTicket,SupportTicketEvent,AcademicCalendarDay
from .academic_engine import member,get,parse,log
ROLES=[r[0] for r in Membership._meta.get_field('role').choices if r[0]!='company']
AGENTS=['admin','principal','faculty','admissions','finance','warden','coe','tpo','tpo_assistant']
def deadline(m,now,days):
    local=timezone.localtime(now)
    holidays=set(AcademicCalendarDay.objects.filter(period__institution=m.institution,period__active=True,kind='holiday',day__gte=local.date(),day__lte=local.date()+timedelta(days=60)).values_list('day',flat=True))
    remaining=days
    for _ in range(90):
        local+=timedelta(days=1)
        if local.weekday()<5 and local.date() not in holidays:
            remaining-=1
            if not remaining:return local
    raise ValidationError('Cannot calculate deadline.')
class New(serializers.Serializer):
    title=serializers.CharField(max_length=150)
    description=serializers.CharField(max_length=6000)
    category=serializers.ChoiceField(choices=['query','incident','change'])
class Update(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    note=serializers.CharField(max_length=4000)
class Assign(Update):
    assignee=serializers.IntegerField(min_value=1)
def scoped(m):
    from django.db.models import Q
    q=SupportTicket.objects.filter(institution=m.institution)
    return q if m.role=='admin' else q.filter(Q(requester=m)|Q(assignee=m))
def view(r,now):
    return {'id':r.pk,'reference':str(r.reference),'title':r.title,'description':r.description,'category':r.category,'status':r.status,'requester':r.requester.user.username,'assignee':r.assignee.user.username if r.assignee_id else None,'requester_id':r.requester_id,'assignee_id':r.assignee_id,'created_at':r.created_at,'response_due':r.response_due,'resolution_due':r.resolution_due,'responded_at':r.responded_at,'resolved_at':r.resolved_at,'response_breached':(r.responded_at or now)>r.response_due,'resolution_breached':(r.resolved_at or now)>r.resolution_due,'escalations':list(r.escalations.values('kind','created_at')),'events':list(r.events.order_by('pk').values('action','note','actor__user__username','created_at'))}
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,ROLES)
    now=timezone.now()
    q=scoped(m).select_related('requester__user','assignee__user')
    result={'membership_id':m.pk,'tickets':[view(r,now) for r in q.order_by('-pk')[:200]],'total':q.count()}
    if m.role=='admin':
        result['agents']=list(Membership.objects.filter(institution=m.institution,role__in=AGENTS,user__is_active=True).values('id','user__username','role'))
    response=Response(result);response['Cache-Control']='private, no-store';return response
@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,ROLES)
    if action=='scan':
        if m.role!='admin':raise PermissionDenied()
        from .escalations import scan
        return Response({'created':scan(m.institution)},status=201)
    schemas={'create':New,'assign':Assign,'respond':Update,'comment':Update,'resolve':Update,'close':Update}
    if action not in schemas:raise NotFound()
    d=parse(schemas[action],request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        now=timezone.now()
        if action=='create':
            row=SupportTicket.objects.create(institution=m.institution,requester=m,response_due=deadline(m,now,2),resolution_due=deadline(m,now,10 if d['category']=='change' else 2),**d)
            note='Ticket created.'
        else:
            row=get(scoped(m),d['id'])
            note=d['note']
            operator=m.role=='admin' or row.assignee_id==m.pk
            if row.status=='closed':raise ValidationError('Ticket is closed.')
            if action=='assign':
                if m.role!='admin':raise PermissionDenied()
                if row.status=='resolved':raise ValidationError('Resolved tickets cannot be reassigned.')
                row.assignee=get(Membership.objects.filter(institution=m.institution,role__in=AGENTS,user__is_active=True),d['assignee'])
                row.status='assigned'
            elif action=='respond':
                if not operator:raise PermissionDenied()
                if row.status=='resolved':raise ValidationError('Ticket already resolved.')
                if row.responded_at is None:row.responded_at=now
            elif action=='resolve':
                if not operator:raise PermissionDenied()
                if row.status=='resolved':raise ValidationError('Ticket already resolved.')
                row.responded_at=row.responded_at or now;row.resolved_at=now;row.status='resolved'
            elif action=='close':
                if row.requester_id!=m.pk and m.role!='admin':raise PermissionDenied()
                if row.status!='resolved':raise ValidationError('Resolve before closing.')
                row.status='closed'
            row.save()
        SupportTicketEvent.objects.create(ticket=row,actor=m,action=action,note=note)
        log(m,'support.'+action,row)
    return Response({'id':row.pk},status=201)
