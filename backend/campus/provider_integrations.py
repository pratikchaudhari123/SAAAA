"""Read-only Tally and Razorpay test-mode integration. No secrets in UI or database."""
import os, json, base64, hmac, hashlib, re
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import URLError
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError,PermissionDenied,NotFound
from rest_framework.response import Response
from .models import Institution,FeeAccount,GatewayOrder,TallySnapshot
from .academic_engine import member,get,parse,log

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def exchange(url,body=None,headers=None,limit=2000000):
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(Request(url,data=body,headers=headers or {}),timeout=8) as r:
            data=r.read(limit+1)
            if len(data)>limit:raise ValidationError('Provider response exceeds allowed size.')
            return data
    except (URLError,OSError,ValueError):raise ValidationError('Provider connection failed. Check the approved endpoint and service configuration.')

def tally_settings(m):
    url=os.getenv('SAAAA_TALLY_URL','');company=os.getenv('SAAAA_TALLY_COMPANY','')
    if os.getenv('SAAAA_TALLY_TENANT')!=m.institution.slug or not url or not company:return None
    u=urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment or len(company)>200:raise ValidationError('Invalid server-side Tally configuration.')
    return url,company

def tally_read(url,company):
    envelope=ET.Element('ENVELOPE');header=ET.SubElement(envelope,'HEADER')
    for k,v in [('VERSION','1'),('TALLYREQUEST','Export'),('TYPE','Collection'),('ID','SAAAA Ledger List')]:ET.SubElement(header,k).text=v
    desc=ET.SubElement(ET.SubElement(envelope,'BODY'),'DESC')
    vars=ET.SubElement(desc,'STATICVARIABLES');ET.SubElement(vars,'SVCURRENTCOMPANY').text=company;ET.SubElement(vars,'SVEXPORTFORMAT').text='$$SysName:XML'
    collection=ET.SubElement(ET.SubElement(ET.SubElement(desc,'TDL'),'TDLMESSAGE'),'COLLECTION',NAME='SAAAA Ledger List',ISMODIFY='No',ISFIXED='No')
    ET.SubElement(collection,'TYPE').text='Ledger'
    ET.SubElement(collection,'NATIVEMETHOD').text='Name,Parent,ClosingBalance'
    raw=exchange(url,ET.tostring(envelope,encoding='utf-8'),{'Content-Type':'text/xml; charset=utf-8'})
    if re.search(br'<!DOCTYPE|<!ENTITY',raw,re.I) or b'\x00' in raw:raise ValidationError('Unsafe or unsupported Tally XML encoding.')
    try:root=ET.fromstring(raw)
    except ET.ParseError:raise ValidationError('Tally did not return valid ledger XML.')
    if root.find('.//LINEERROR') is not None or root.findtext('./HEADER/STATUS')=='0':raise ValidationError('Tally rejected the ledger export. Check company, permissions and version.')
    rows=[]
    for node in root.iter('LEDGER'):
        name=node.get('NAME') or node.findtext('NAME') or ''
        if not name:continue
        rows.append({'name':name[:200],'parent':(node.findtext('PARENT') or '')[:200],'closing_balance':(node.findtext('CLOSINGBALANCE') or '')[:100]})
        if len(rows)>2000:raise ValidationError('Ledger export exceeds evaluation limit.')
    if not rows:raise ValidationError('No ledger rows returned. Verify selected company and export format.')
    return rows,hashlib.sha256(raw).hexdigest()

def razor_settings(m):
    key=os.getenv('SAAAA_RAZORPAY_KEY_ID','');secret=os.getenv('SAAAA_RAZORPAY_KEY_SECRET','')
    if os.getenv('SAAAA_RAZORPAY_TENANT')!=m.institution.slug or not key.startswith('rzp_test_') or not secret:return None
    return key,secret

def razor_call(config,path,payload=None):
    key,secret=config
    raw=exchange('https://api.razorpay.com/v1/'+path,json.dumps(payload).encode() if payload is not None else None,{'Authorization':'Basic '+base64.b64encode((key+':'+secret).encode()).decode(),'Content-Type':'application/json'},100000)
    try:result=json.loads(raw)
    except ValueError:raise ValidationError('Invalid payment provider response.')
    if not isinstance(result,dict):raise ValidationError('Invalid payment provider response.')
    return result

def accounts(m):
    q=FeeAccount.objects.filter(student__institution=m.institution)
    return q.filter(student__portal_user=m.user,student__status='Active') if m.role=='student' else q

def amount_due(a):return a.assessed-(a.receipts.aggregate(v=Sum('amount'))['v'] or Decimal('0'))

class Start(serializers.Serializer):
    account=serializers.IntegerField(min_value=1)
class Verify(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)
    payment_id=serializers.RegexField(r'\Apay_[A-Za-z0-9]{1,64}\Z')
    signature=serializers.RegexField(r'\A[0-9a-f]{64}\Z')
class Ref(serializers.Serializer):
    id=serializers.IntegerField(min_value=1)

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','finance','student'])
    q=accounts(m); orders=GatewayOrder.objects.filter(account__in=q).order_by('-pk')[:100]
    data={'razorpay_test_ready':bool(razor_settings(m)),'accounts':[{'id':a.pk,'period':a.period,'student_id':a.student.student_id,'outstanding':str(amount_due(a))} for a in q.select_related('student')[:200]],'orders':list(orders.values('id','account_id','reference','amount_paise','provider_order','provider_payment','status','created_at','verified_at'))}
    if m.role!='student':
        data['tally_ready']=bool(tally_settings(m))
        snapshot=TallySnapshot.objects.filter(institution=m.institution).order_by('-pk').first()
        data['tally']=None if not snapshot else {'company':snapshot.company,'rows':snapshot.rows,'sha256':snapshot.sha256,'created_at':snapshot.created_at}
    response=Response(data);response['Cache-Control']='private, no-store';return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','finance','student'])
    if action=='tally':
        if m.role=='student':raise PermissionDenied()
        config=tally_settings(m)
        if not config:raise ValidationError('Tally not configured for this institution.')
        rows,digest=tally_read(*config)
        with transaction.atomic():
            row=TallySnapshot.objects.create(institution=m.institution,actor=m.user,company=config[1],rows=rows,sha256=digest)
            log(m,'provider.tally.read',row)
        return Response({'id':row.pk,'rows':len(rows)},status=201)
    config=razor_settings(m)
    if not config:raise ValidationError('Razorpay test credentials not configured for this institution. Live keys are not accepted.')
    if action=='start':
        if m.role!='student':raise PermissionDenied()
        d=parse(Start,request)
        # Test only, never posts a financial receipt. Reuse recent pending orders.
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            a=get(accounts(m),d['account'])
            due=amount_due(a)
            if due<=0:raise ValidationError('No outstanding fee.')
            paise=int(due*100)
            row=GatewayOrder.objects.filter(account=a,status='created',amount_paise=paise,created_at__gte=timezone.now()-timedelta(days=7)).first()
            if not row:
                from uuid import uuid4
                ref=uuid4()
                result=razor_call(config,'orders',{'amount':paise,'currency':'INR','receipt':str(ref),'partial_payment':False})
                oid=result.get('id','')
                if not re.fullmatch(r'order_[A-Za-z0-9]{1,64}',str(oid)) or result.get('amount')!=paise or result.get('currency')!='INR':raise ValidationError('Provider order mismatch.')
                row=GatewayOrder.objects.create(account=a,created_by=m.user,reference=ref,amount_paise=paise,provider_order=oid)
                log(m,'provider.test.order',row)
        return Response({'id':row.pk,'order_id':row.provider_order,'amount':row.amount_paise,'currency':'INR','key':config[0]},status=201)
    if action not in ('verify','refresh'):raise NotFound()
    d=parse(Verify if action=='verify' else Ref,request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        row=get(GatewayOrder.objects.filter(account__in=accounts(m)),d['id'])
        if action=='verify':
            expected=hmac.new(config[1].encode(),(row.provider_order+'|'+d['payment_id']).encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,d['signature']):raise ValidationError('Payment signature invalid.')
            payment=razor_call(config,'payments/'+d['payment_id'])
        else:
            result=razor_call(config,'orders/'+row.provider_order+'/payments')
            items=result.get('items',[])
            payment=next((p for p in items if isinstance(p,dict) and p.get('status')=='captured'),None)
            if not payment:
                if row.status!='captured' and row.created_at<timezone.now()-timedelta(days=7):
                    row.status='expired';row.save(update_fields=['status'])
                return Response({'status':row.status,'message':'No captured payment found. Expiry is local, not provider cancellation.'})
        pid=payment.get('id','')
        if not re.fullmatch(r'pay_[A-Za-z0-9]{1,64}',str(pid)) or payment.get('order_id')!=row.provider_order or payment.get('amount')!=row.amount_paise or payment.get('currency')!='INR' or payment.get('status')!='captured' or payment.get('amount_refunded',0)!=0:raise ValidationError('Captured payment details do not match the order.')
        if row.provider_payment and row.provider_payment!=pid:raise ValidationError('Conflicting payment reference.')
        if GatewayOrder.objects.filter(provider_payment=pid).exclude(pk=row.pk).exists():raise ValidationError('Payment reference already used.')
        if row.status!='captured':
            row.provider_payment=pid;row.status='captured';row.verified_at=timezone.now();row.save(update_fields=['provider_payment','status','verified_at'])
            log(m,'provider.test.verified',row)
    return Response({'status':row.status,'message':'Test capture verified. No actual fee receipt or accounting entry posted.'})
