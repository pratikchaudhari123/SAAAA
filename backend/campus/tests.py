from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Institution, Membership, Student, AuditEvent
class IsolationTests(TestCase):
    def setUp(self):
        self.a=Institution.objects.create(name='A',slug='a')
        self.b=Institution.objects.create(name='B',slug='b')
        self.user=get_user_model().objects.create_user(username='testuser',password='test-only-password')
        Membership.objects.create(user=self.user,institution=self.a,role='admin')
        self.client.force_login(self.user)
    def test_other_tenant_denied(self):
        self.assertEqual(self.client.get('/api/institutions/b/students/').status_code,403)
    def test_create_and_audit(self):
        data={'student_id':'DEMO-1','name':'Demo Student','email':'student@example.invalid','program':'Engineering','year':1,'status':'Active'}
        self.assertEqual(self.client.post('/api/institutions/a/students/',data,content_type='application/json').status_code,201)
        self.assertEqual(Student.objects.filter(institution=self.a).count(),1)
        self.assertEqual(AuditEvent.objects.filter(actor=self.user).count(),1)
    def test_anonymous_denied(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/institutions/a/students/').status_code,403)
    def test_viewer_cannot_create(self):
        Membership.objects.filter(user=self.user).update(role='viewer')
        self.assertEqual(self.client.post('/api/institutions/a/students/',{'student_id':'X','name':'Demo','email':'demo@example.invalid','program':'Engineering','year':1},content_type='application/json').status_code,403)

    def test_creation_cannot_bypass_admission(self):
        data={'student_id':'DEMO-BYPASS','name':'Demo Student','email':'student@example.invalid','program':'Engineering','year':1,'status':'Active'}
        self.assertEqual(self.client.post('/api/institutions/a/students/',data,content_type='application/json').status_code,201)
        self.assertEqual(Student.objects.get(institution=self.a,student_id='DEMO-BYPASS').status,'Pending')
    def test_health_checks_database(self):
        response=self.client.get('/api/health/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['database'],'connected')

    def test_session_status(self):
        self.assertTrue(self.client.get('/api/session/').json()['authenticated'])
        self.client.logout()
        self.assertFalse(self.client.get('/api/session/').json()['authenticated'])

    def test_live_operations(self):
        from django.utils import timezone
        from .models import AttendanceEntry, FeeAccount, FeeReceipt, HostelBed, HostelCheck
        Student.objects.create(institution=self.a,student_id='S1',name='Example',email='s1@example.invalid',program='Engineering',year=1,status='Active')
        base='/api/institutions/a/operations/'
        def post(area,data):
            return self.client.post(base+area+'/',data,content_type='application/json')
        entry={'student_id':'S1','day':str(timezone.localdate()),'course':'DEMO101','present':True}
        self.assertEqual(post('attendance',entry).status_code,201)
        self.assertEqual(post('attendance',{**entry,'present':False}).status_code,201)
        self.assertEqual(AttendanceEntry.objects.count(),1)
        self.assertFalse(AttendanceEntry.objects.get().present)
        self.assertEqual(post('fees',{'student_id':'S1','period':'2026-27','assessed':'1000.00'}).status_code,201)
        account=FeeAccount.objects.get()
        self.assertEqual(post('receipts',{'account':account.pk,'amount':'400.00','method':'cash'}).status_code,201)
        self.assertEqual(post('receipts',{'account':account.pk,'amount':'601.00','method':'bank'}).status_code,400)
        self.assertEqual(FeeReceipt.objects.count(),1)
        self.assertEqual(self.client.get(base+'fees/').json()[0]['balance'],'600.00')
        self.assertEqual(post('beds',{'code':'H1-A','student_id':'S1'}).status_code,201)
        self.assertEqual(post('beds',{'code':'H1-B','student_id':'S1'}).status_code,400)
        self.assertEqual(HostelBed.objects.count(),1)
        self.assertEqual(post('hostel_checks',{'code':'H1-A','status':'present'}).status_code,201)
        self.assertEqual(HostelCheck.objects.count(),1)
        self.assertGreaterEqual(AuditEvent.objects.count(),6)
        self.assertEqual(self.client.get('/api/institutions/b/operations/fees/').status_code,403)
        Membership.objects.filter(user=self.user).update(role='viewer')
        self.assertEqual(self.client.get(base+'fees/').status_code,403)
        self.assertEqual(post('attendance',entry).status_code,403)
