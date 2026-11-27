"""Deployment-configured CIDR restrictions and redacted request audit."""
import ipaddress,os,re
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .models import Membership,RequestAudit
CRITICAL={'ledger','operations','provider-integrations','permissions','accounts','evaluation','exam-preparation','registration','audit','connect','security-audit'}
TENANT=re.compile(r'^/api/institutions/([A-Za-z0-9_-]+)/([^/]+)/')
def client_ip(request):
    # Trust the immediate peer only. A reverse proxy must enforce the real-client ACL itself.
    try:return ipaddress.ip_address(request.META.get('REMOTE_ADDR',''))
    except ValueError:return None
def permitted(request):
    raw=os.getenv('SAAAA_CRITICAL_CIDRS','').strip()
    if not raw:return True
    try:
        nets=[ipaddress.ip_network(x.strip(),strict=True) for x in raw.split(',')]
        addr=client_ip(request)
        return addr is not None and any(addr in net for net in nets)
    except ValueError:return False
class CampusSecurity(MiddlewareMixin):
    def process_request(self,request):
        match=TENANT.match(request.path)
        if match and request.user.is_authenticated:
            request.campus_audit_member=Membership.objects.filter(user=request.user,institution__slug=match[1]).first()
            if match[2] in CRITICAL and not permitted(request):
                return JsonResponse({'detail':'Critical application is restricted to approved network addresses.'},status=403)
    def process_response(self,request,response):
        m=getattr(request,'campus_audit_member',None)
        if m and request.method in ('POST','PUT','PATCH','DELETE'):
            # Never capture body, query string, cookies, authorization headers or secrets.
            match=TENANT.match(request.path)
            safe_path='/api/institutions/'+m.institution.slug+'/'+match[2]+'/' if match else '/api/institutions/'
            RequestAudit.objects.create(institution=m.institution,actor=m.user,method=request.method,path=safe_path,ip=str(client_ip(request)) if client_ip(request) else None,status=response.status_code)
        return response
