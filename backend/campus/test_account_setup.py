from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from .models import Institution,Membership,Student,AuditEvent

class AccountSetupTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='A',slug='accounts-a')
        self.j=Institution.objects.create(name='B',slug='accounts-b')
        self.admin=get_user_model().objects.create_user(username='account-admin',password='test-only')
        self.viewer=get_user_model().objects.create_user(username='account-viewer',password='test-only')
        Membership.objects.create(institution=self.i,user=self.admin,role='admin')
        Membership.objects.create(institution=self.i,user=self.viewer,role='viewer')
        self.s=Student.objects.create(institution=self.i,student_id='S1',name='Student One',email='one@example.invalid',program='Engineering',year=1,status='Active')
        Student.objects.create(institution=self.j,student_id='OTHER',name='Other Student',email='other@example.invalid',program='Engineering',year=1,status='Active')
        self.client.force_login(self.admin)
        self.url='/api/institutions/accounts-a/accounts/'
    def post(self,data,status):
        r=self.client.post(self.url,data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r
    def test_create_student_and_private_login(self):
        r=self.post({'username':'student.one','role':'student','student_id':'S1'},201)
        self.assertEqual(r['Cache-Control'],'no-store')
        info=r.json()
        self.s.refresh_from_db()
        self.assertEqual(self.s.portal_user.username,'student.one')
        self.assertTrue(self.s.portal_user.check_password(info['password']))
        self.assertNotIn(info['password'],self.client.get(self.url).content.decode())
        self.assertTrue(AuditEvent.objects.filter(institution=self.i,actor=self.admin,action='account.provision').exists())
        c=Client(enforce_csrf_checks=True)
        c.get('/api/csrf/')
        response=c.post('/api/login/',{'username':info['username'],'password':info['password']},content_type='application/json',HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
        self.assertEqual(response.status_code,200)
        self.assertEqual(c.get('/api/institutions/accounts-a/my-campus/').json()['profile']['student_id'],'S1')
        self.assertEqual(c.get(self.url).status_code,403)
        self.post({'username':'second.student','role':'student','student_id':'S1'},400)
        self.assertFalse(get_user_model().objects.filter(username='second.student').exists())
    def test_permissions_and_validation(self):
        self.post({'username':'foreign.student','role':'student','student_id':'OTHER'},400)
        self.post({'username':'missing.student','role':'student'},400)
        self.post({'username':'bad.staff','role':'faculty','student_id':'S1'},400)
        self.post({'username':'new.admin','role':'admin'},400)
        self.post({'username':'new.faculty','role':'faculty'},201)
        self.post({'username':'new.faculty','role':'faculty'},400)
        self.assertEqual(self.client.get('/api/institutions/accounts-b/accounts/').status_code,403)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.post({'username':'unauthorized','role':'faculty'},403)
