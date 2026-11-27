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
