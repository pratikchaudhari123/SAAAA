from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution, Membership, Student, IntegrationSource, IntegrationEvent, StudentImportBatch, AttendanceEntry, AuditEvent

class ConnectTests(TestCase):
    def setUp(self):
        self.a=Institution.objects.create(name='Campus A',slug='connect-a')
        self.b=Institution.objects.create(name='Campus B',slug='connect-b')
        self.user=get_user_model().objects.create_user(username='connect-admin',password='test-only')
        self.other=get_user_model().objects.create_user(username='connect-viewer',password='test-only')
        Membership.objects.create(institution=self.a,user=self.user,role='admin')
        Membership.objects.create(institution=self.b,user=self.other,role='admin')
        self.client.force_login(self.user)
        self.root='/api/institutions/connect-a/connect/'
        self.machine=Client(enforce_csrf_checks=True)
    def post(self,path,data):
        return self.client.post(self.root+path,data,content_type='application/json')
    def source(self):
        r=self.post('sources/',{'name':'Gate A','purpose':'hostel'})
        self.assertEqual(r.status_code,201)
        self.assertEqual(r['Cache-Control'],'no-store')
        return r.json()
    def event(self,token,data):
        return self.machine.post('/api/connect/events/',data,content_type='application/json',HTTP_AUTHORIZATION='Bearer '+token)
    def payload(self):
        return {'external_id':'event-001','subject_ref':'STU-001','event_type':'in','occurred_at':timezone.now().isoformat()}
    def test_device_ingestion_and_idempotency(self):
        s=self.source()
        self.assertNotEqual(IntegrationSource.objects.get(pk=s['id']).token_digest,s['token'])
        self.assertNotIn(s['token'],self.client.get(self.root+'sources/').content.decode())
        p=self.payload()
        self.assertEqual(self.event(s['token'],p).status_code,201)
        self.assertEqual(self.event(s['token'],p).status_code,200)
        self.assertEqual(self.event(s['token'],{**p,'event_type':'out'}).status_code,409)
        self.assertEqual(IntegrationEvent.objects.count(),1)
        self.assertEqual(AttendanceEntry.objects.count(),0)
        self.assertEqual(self.client.get(self.root+'events/').json()['total'],1)
        self.assertIsNotNone(IntegrationSource.objects.get(pk=s['id']).last_received_at)
    def test_device_tokens_and_payload_validation(self):
        s=self.source()
        p=self.payload()
        self.assertEqual(self.event('invalid',p).status_code,401)
        self.assertEqual(self.client.post('/api/connect/events/',p,content_type='application/json').status_code,401)
        self.assertEqual(self.event(s['token'],{**p,'face_image':'not-allowed'}).status_code,400)
        self.assertEqual(self.event(s['token'],{**p,'occurred_at':'2026-01-01T12:00:00'}).status_code,400)
        self.assertEqual(self.event(s['token'],{**p,'subject_ref':'invalid reference'}).status_code,400)
        rotated=self.post('sources/'+str(s['id'])+'/action/',{'action':'rotate'}).json()
        self.assertEqual(self.event(s['token'],p).status_code,401)
        self.assertEqual(self.event(rotated['token'],p).status_code,201)
        self.assertEqual(self.post('sources/'+str(s['id'])+'/action/',{'action':'disable'}).status_code,200)
        self.assertEqual(self.event(rotated['token'],p).status_code,401)
    def test_connect_tenant_and_role_boundaries(self):
        s=self.source()
        self.assertEqual(self.event(s['token'],self.payload()).status_code,201)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.root+'sources/').status_code,403)
        self.assertEqual(self.client.get('/api/institutions/connect-b/connect/events/').json()['total'],0)
        self.assertEqual(self.client.post('/api/institutions/connect-b/connect/sources/'+str(s['id'])+'/action/',{'action':'disable'},content_type='application/json').status_code,404)
        Membership.objects.filter(user=self.other).update(role='viewer')
        self.assertEqual(self.client.get('/api/institutions/connect-b/connect/sources/').status_code,403)
        self.assertEqual(self.client.post('/api/institutions/connect-b/connect/student-import/',{'mode':'preview','csv':'x'},content_type='application/json').status_code,403)
    def test_csv_preview_apply_and_preserve(self):
        Student.objects.create(institution=self.a,student_id='OLD',name='Original',email='old@example.invalid',program='Engineering',year=2,status='Active')
        raw='student_id,name,email,program,year\nOLD,Changed,old@example.invalid,Engineering,3\nNEW,New Student,new@example.invalid,Engineering,1\n'
        preview=self.post('student-import/',{'mode':'preview','csv':raw})
        self.assertEqual(preview.status_code,200)
        p=preview.json()
        self.assertEqual((p['new_rows'],p['existing_rows']),(1,1))
        self.assertEqual(Student.objects.count(),1)
        self.assertEqual(self.post('student-import/',{'mode':'apply','csv':raw,'file_digest':'wrong'}).status_code,400)
        result=self.post('student-import/',{'mode':'apply','csv':raw,'file_digest':p['file_digest']})
        self.assertEqual(result.status_code,201)
        self.assertEqual(Student.objects.get(student_id='OLD').name,'Original')
        self.assertEqual(Student.objects.get(student_id='NEW').status,'Pending')
        self.assertEqual(Student.objects.filter(institution=self.b).count(),0)
        self.assertEqual(StudentImportBatch.objects.get().created_count,1)
        self.assertTrue(AuditEvent.objects.filter(action='integration.student_import',actor=self.user).exists())
        self.assertEqual(self.post('student-import/',{'mode':'preview','csv':raw}).json()['new_rows'],0)
    def test_invalid_csv_no_partial_write(self):
        raw='student_id,name,email,program,year\nNEW,New Student,new@example.invalid,Engineering,1\nBAD,Bad Student,not-an-email,Engineering,99\n'
        p=self.post('student-import/',{'mode':'preview','csv':raw}).json()
        self.assertEqual(len(p['errors']),1)
        self.assertEqual(self.post('student-import/',{'mode':'apply','csv':raw,'file_digest':p['file_digest']}).status_code,400)
        self.assertEqual(Student.objects.count(),0)
        self.assertEqual(StudentImportBatch.objects.count(),0)
