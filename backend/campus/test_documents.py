from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,FeeAccount,FeeReceipt,InstitutionalRoleGrant,CertificateRequest
from uuid import uuid4
class DocumentTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='A',slug='docs-a')
        self.j=Institution.objects.create(name='B',slug='docs-b')
        self.users={};self.members={}
        for name,role in [('admin','admin'),('finance','finance'),('faculty','faculty'),('student','student'),('other','student'),('foreign','admin')]:
            u=get_user_model().objects.create_user(username='doc-'+name)
            self.users[name]=u
            self.members[name]=Membership.objects.create(institution=self.j if name=='foreign' else self.i,user=u,role=role)
        for name in ['student','other']:
            Student.objects.create(institution=self.i,portal_user=self.users[name],student_id=name,name=name,email=name+'@example.invalid',program='Engineering',year=1,status='Active')
        self.root='/api/institutions/docs-a/'
        self.now=timezone.now()
        self.login('admin')
    def login(self,name): self.client.force_login(self.users[name])
    def post(self,path,data,status=201):
        r=self.client.post(self.root+path+'/',data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def view(self,path='documents'):
        r=self.client.get(self.root+path+'/')
        self.assertEqual(r.status_code,200,r.content)
        return r.json()
    def test_role_inheritance_expiry_and_revocation(self):
        parent=self.post('permissions/role',{'name':'Academic clearance','permissions':['document.academic']})['id']
        child=self.post('permissions/role',{'name':'Document officer','parent':parent,'permissions':['document.issue']})['id']
        self.assertEqual(set(next(r for r in self.view('permissions')['roles'] if r['id']==child)['effective']),{'document.academic','document.issue'})
        payload={'role':child,'membership':self.members['faculty'].pk,'starts':(self.now-timedelta(minutes=1)).isoformat(),'ends':(self.now+timedelta(minutes=30)).isoformat(),'reason':'Synthetic delegation'}
        grant=self.post('permissions/grant',payload)['id']
        self.post('permissions/grant',{**payload,'membership':self.members['student'].pk},404)
        self.post('permissions/grant',{**payload,'membership':self.members['foreign'].pk},404)
        self.login('faculty')
        self.assertEqual(set(self.view()['capabilities']),{'document.issue','document.academic'})
        self.post('permissions/role',{'name':'Escalate','permissions':['document.report']},403)
        self.login('admin')
        self.post('permissions/revoke',{'id':grant})
        self.login('faculty')
        self.assertEqual(self.view()['capabilities'],[])
        self.login('admin')
        future=self.post('permissions/grant',{**payload,'starts':(self.now+timedelta(minutes=5)).isoformat()})['id']
        self.login('faculty')
        self.assertEqual(self.view()['capabilities'],[])
        InstitutionalRoleGrant.objects.filter(pk=future).update(starts=self.now-timedelta(minutes=5),ends=self.now-timedelta(minutes=1))
        self.assertEqual(self.view()['capabilities'],[])
    def test_issue_clearance_duplicate_and_privacy(self):
        p=self.post('documents/policy',{'code':'B1','kind':'bonafide','title':'Bonafide','text':'Student {student_name} at {institution}.','allow_duplicate':True,'clearance_units':['finance']})['id']
        s=Student.objects.get(portal_user=self.users['student'])
        fee=FeeAccount.objects.create(student=s,period='QA',assessed=100)
        self.login('student')
        self.post('documents/apply',{'policy':p,'copy_kind':'duplicate','reason':'Synthetic'},400)
        a=self.post('documents/apply',{'policy':p,'copy_kind':'original','reason':'Synthetic'})['id']
        self.post('documents/apply',{'policy':p,'copy_kind':'original','reason':'Again'},400)
        self.post('documents/review',{'id':a,'decision':'issued','note':'Unauthorized','confirmed':True},403)
        self.login('other')
        self.assertEqual(self.view()['requests'],[])
        self.login('admin')
        review={'id':a,'decision':'issued','note':'Synthetic approval','confirmed':True}
        self.post('documents/review',review,400)
        self.login('finance')
        clearance={'id':a,'unit':'finance','cleared':True,'note':'QA reconciliation'}
        self.post('documents/clearance',clearance,400)
        FeeReceipt.objects.create(account=fee,reference=uuid4(),amount=100,method='cash',recorded_by=self.users['finance'])
        self.post('documents/clearance',clearance)
        self.login('admin')
        self.post('documents/review',review)
        r=CertificateRequest.objects.get(pk=a)
        self.assertEqual(r.issued_snapshot['text'],'Student student at A.')
        self.login('student')
        self.assertEqual(self.view()['requests'][0]['serial'],str(r.serial))
        d=self.post('documents/apply',{'policy':p,'copy_kind':'duplicate','reason':'Lost copy'})['id']
        self.login('admin')
        self.post('documents/review',{'id':a,'decision':'revoked','note':'QA revocation'})
        self.post('documents/clearance',{'id':d,'unit':'finance','cleared':True,'note':'QA'})
        self.post('documents/review',{**review,'id':d},400)
        self.login('foreign')
        self.assertEqual(self.client.get(self.root+'documents/').status_code,403)

    def test_delegated_issue_is_enforced_at_mutation(self):
        policy=self.post('documents/policy',{'code':'ID1','kind':'student_id','title':'ID','text':'Student {student_id}'})['id']
        role=self.post('permissions/role',{'name':'Temporary issuer','permissions':['document.issue']})['id']
        self.login('student')
        req=self.post('documents/apply',{'policy':policy,'copy_kind':'original','reason':'Synthetic'})['id']
        self.login('faculty')
        review={'id':req,'decision':'issued','note':'Synthetic approval','confirmed':True}
        self.post('documents/review',review,403)
        self.login('admin')
        grant=self.post('permissions/grant',{'role':role,'membership':self.members['faculty'].pk,'starts':(self.now-timedelta(minutes=1)).isoformat(),'ends':(self.now+timedelta(minutes=20)).isoformat(),'reason':'Temporary duty'})['id']
        self.login('faculty')
        self.post('documents/review',review)
        self.login('admin')
        self.post('permissions/revoke',{'id':grant})
        self.login('faculty')
        self.post('documents/review',{'id':req,'decision':'revoked','note':'No authority'},403)
        self.login('student')
        self.assertEqual(self.view()['requests'][0]['status'],'issued')
        self.assertNotIn('fee_assessed',self.view()['requests'][0]['issued'])
