import hashlib,hmac,os
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,FeeAccount,FeeReceipt,GatewayOrder,TallySnapshot,RequestAudit,SupportTicket,SupportEscalation
from .provider_integrations import tally_read
from .escalations import scan

class ProviderTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='A',slug='provider-a')
        self.j=Institution.objects.create(name='B',slug='provider-b')
        self.users={};self.members={}
        for name,role in [('admin','admin'),('student','student'),('other','student'),('foreign','admin')]:
            u=get_user_model().objects.create_user(username='provider-'+name);self.users[name]=u
            self.members[name]=Membership.objects.create(institution=self.j if name=='foreign' else self.i,user=u,role=role)
        s=Student.objects.create(institution=self.i,student_id='QA',name='QA',email='qa@example.invalid',program='Engineering',year=1,status='Active',portal_user=self.users['student'])
        self.fee=FeeAccount.objects.create(student=s,period='QA',assessed=100)
        self.root='/api/institutions/provider-a/'
    def login(self,name):self.client.force_login(self.users[name])
    def post(self,path,data,status=201):
        r=self.client.post(self.root+path+'/',data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content);return r.json()
    @patch.dict(os.environ,{'SAAAA_RAZORPAY_TENANT':'provider-a','SAAAA_RAZORPAY_KEY_ID':'rzp_test_synthetic','SAAAA_RAZORPAY_KEY_SECRET':'synthetic'})
    @patch('campus.provider_integrations.razor_call')
    def test_test_mode_order_signature_and_capture(self,call):
        self.login('student')
        call.return_value={'id':'order_QA','amount':10000,'currency':'INR'}
        row=self.post('provider-integrations/start',{'account':self.fee.pk})
        self.assertEqual(row['amount'],10000)
        self.assertEqual(self.post('provider-integrations/start',{'account':self.fee.pk})['id'],row['id'])
        self.assertEqual(call.call_count,1)
        self.post('provider-integrations/verify',{'id':row['id'],'payment_id':'pay_QA','signature':'0'*64},400)
        sig=hmac.new(b'synthetic',b'order_QA|pay_QA',hashlib.sha256).hexdigest()
        call.return_value={'id':'pay_QA','order_id':'order_QA','amount':10000,'currency':'INR','status':'authorized'}
        self.post('provider-integrations/verify',{'id':row['id'],'payment_id':'pay_QA','signature':sig},400)
        call.return_value['status']='captured'
        self.post('provider-integrations/verify',{'id':row['id'],'payment_id':'pay_QA','signature':sig},200)
        self.assertEqual(GatewayOrder.objects.get().status,'captured')
        self.assertFalse(FeeReceipt.objects.exists())
        self.login('other')
        self.post('provider-integrations/refresh',{'id':row['id']},404)
        with patch.dict(os.environ,{'SAAAA_RAZORPAY_KEY_ID':'rzp_live_forbidden'}):
            self.login('student');self.post('provider-integrations/start',{'account':self.fee.pk},400)
    @patch.dict(os.environ,{'SAAAA_TALLY_TENANT':'provider-a','SAAAA_TALLY_URL':'http://127.0.0.1:9000','SAAAA_TALLY_COMPANY':'QA'})
    @patch('campus.provider_integrations.exchange')
    def test_tally_read_only(self,exchange):
        exchange.return_value=b'<ENVELOPE><HEADER><STATUS>1</STATUS></HEADER><BODY><LEDGER NAME="Cash"><PARENT>Cash-in-Hand</PARENT><CLOSINGBALANCE>100</CLOSINGBALANCE></LEDGER></BODY></ENVELOPE>'
        self.login('admin')
        self.post('provider-integrations/tally',{})
        self.assertIn(b'<TALLYREQUEST>Export</TALLYREQUEST>',exchange.call_args.args[1])
        self.assertEqual(TallySnapshot.objects.get().rows[0]['name'],'Cash')
        exchange.return_value=b'<!DOCTYPE x [<!ENTITY e "x">]><x>&e;</x>'
        self.post('provider-integrations/tally',{},400)
        self.login('student');self.post('provider-integrations/tally',{},403)
    @patch.dict(os.environ,{'SAAAA_CRITICAL_CIDRS':'192.0.2.0/24'})
    def test_network_restriction_and_redacted_audit(self):
        self.login('admin')
        r=self.client.post(self.root+'operations/fees/',{'student_id':'QA','period':'Denied','assessed':'1.00'},content_type='application/json',REMOTE_ADDR='127.0.0.1',HTTP_X_FORWARDED_FOR='192.0.2.1')
        self.assertEqual(r.status_code,403)
        a=RequestAudit.objects.filter(path__contains='operations').latest('pk')
        self.assertEqual(a.status,403)
        self.assertEqual(a.ip,'127.0.0.1')
        self.assertEqual(self.client.get(self.root+'security-audit/',REMOTE_ADDR='192.0.2.5').status_code,200)
    def test_sla_scan_is_idempotent(self):
        now=timezone.now()
        t=SupportTicket.objects.create(institution=self.i,requester=self.members['student'],title='QA',description='QA',category='query',response_due=now-timedelta(days=1),resolution_due=now-timedelta(days=1))
        self.assertEqual(scan(self.i),2)
        self.assertEqual(scan(self.i),0)
        self.assertEqual(SupportEscalation.objects.filter(ticket=t).count(),2)
