from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution, Membership, Student, CampusNotice, NoticeAcknowledgment, FeedbackSurvey, FeedbackResponse, FeeAccount, FeeReceipt
from uuid import uuid4

class CommunicationTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='A',slug='comm-a')
        self.j=Institution.objects.create(name='B',slug='comm-b')
        self.users={};self.members={}
        for label,role in [('admin','admin'),('principal','principal'),('faculty','faculty'),('company','company'),('s1','student'),('s2','student'),('s3','student'),('s4','student'),('foreign','student')]:
            u=get_user_model().objects.create_user(username='comm-'+label)
            self.users[label]=u
            self.members[label]=Membership.objects.create(institution=self.j if label=='foreign' else self.i,user=u,role=role)
        for label in ['s1','s2','s3','s4']:
            s=Student.objects.create(institution=self.i,portal_user=self.users[label],student_id=label,name=label,email=label+'@example.invalid',program='Engineering',year=1,status='Active')
            fee=FeeAccount.objects.create(student=s,period='QA',assessed=100)
            FeeReceipt.objects.create(account=fee,reference=uuid4(),amount=100 if label!='s4' else 10,method='cash',recorded_by=self.users['admin'])
        self.root='/api/institutions/comm-a/communications/'
        self.now=timezone.now()
        self.login('admin')
    def login(self,label): self.client.force_login(self.users[label])
    def post(self,action,data,status=201):
        r=self.client.post(self.root+action+'/',data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def view(self): return self.client.get(self.root).json()
    def test_scheduled_notice_scope_and_acknowledgment(self):
        payload={'title':'Synthetic task','body':'Complete review','kind':'task','audience':'individual','recipient':self.members['s1'].pk,'starts':(self.now-timedelta(minutes=1)).isoformat(),'ends':(self.now+timedelta(days=1)).isoformat()}
        n=self.post('notice',payload)['id']
        self.post('notice',{**payload,'recipient':self.members['foreign'].pk},404)
        self.post('notice',{**payload,'title':'Future','audience':'all','recipient':None,'starts':(self.now+timedelta(hours=1)).isoformat()})
        self.login('s2')
        self.assertEqual(self.view()['notices'],[])
        self.post('ack',{'id':n},404)
        self.post('notice',payload,403)
        self.login('s1')
        self.assertEqual(len(self.view()['notices']),1)
        self.post('ack',{'id':n})
        self.post('ack',{'id':n},200)
        self.assertEqual(NoticeAcknowledgment.objects.count(),1)
        self.login('company')
        self.assertEqual(self.client.get(self.root).status_code,403)
        self.login('admin')
        self.post('withdraw',{'id':n})
        self.login('s1')
        self.assertEqual(self.view()['notices'],[])
    def test_feedback_eligibility_aggregate_privacy_and_deadline(self):
        payload={'title':'Synthetic infrastructure survey','kind':'infrastructure','scale':'grade','questions':['Quality','Access'],'opens':(self.now-timedelta(minutes=1)).isoformat(),'closes':(self.now+timedelta(days=1)).isoformat(),'min_fee_paid':80}
        survey=self.post('survey',payload)['id']
        self.assertEqual(self.view()['surveys'][0]['invited'],3)
        self.login('s4')
        self.assertEqual(self.view()['surveys'],[])
        self.post('answer',{'id':survey,'scores':[4,4]},404)
        self.login('s1')
        self.post('answer',{'id':survey,'scores':[6,4]},400)
        self.post('answer',{'id':survey,'scores':[4,4]})
        self.post('answer',{'id':survey,'scores':[4,4]},400)
        self.assertNotIn('scores',self.view()['surveys'][0])
        self.login('principal')
        self.assertIsNone(self.view()['surveys'][0]['averages'])
        self.login('s2')
        self.post('answer',{'id':survey,'scores':[3,5]})
        self.login('s3')
        self.post('answer',{'id':survey,'scores':[5,3]})
        FeedbackSurvey.objects.filter(pk=survey).update(opens=self.now-timedelta(days=2),closes=self.now-timedelta(days=1))
        self.login('principal')
        self.assertEqual(self.view()['surveys'][0]['averages'],[4.0,4.0])
        self.assertEqual(FeedbackResponse.objects.count(),3)
        self.login('foreign')
        self.assertEqual(self.client.get(self.root).status_code,403)
