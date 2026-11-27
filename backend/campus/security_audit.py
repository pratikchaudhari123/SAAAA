from rest_framework.decorators import api_view
from rest_framework.response import Response
from .academic_engine import member
from .models import RequestAudit,AuditEvent
import os
@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin'])
    result={'ip_restrictions_configured':bool(os.getenv('SAAAA_CRITICAL_CIDRS','').strip()),'requests':list(RequestAudit.objects.filter(institution=m.institution).order_by('-pk').values('method','path','ip','status','actor__username','created_at')[:200]),'events':list(AuditEvent.objects.filter(institution=m.institution).order_by('-pk').values('action','target','actor__username','created_at')[:200])}
    r=Response(result);r['Cache-Control']='private, no-store';return r
