from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Department,Employee,EmployeePunch,EmployeeLeave,IntegrationEvent

class EmployeeTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='HR A',slug='hr-a')
        self.j=Institution.objects.create(name='HR B',slug='hr-b')
        self.users={}
        self.members={}
        for role in ('admin','principal','faculty','finance','student','foreign'):
            u=get_user_model().objects.create_user(username='hr-'+role,password='test-only')
            self.users[role]=u
            self.members[role]=Membership.objects.create(institution=self.j if role=='foreign' else self.i,user=u,role='faculty' if role=='foreign' else role)
        self.dep=Department.objects.create(institution=self.i,code='QA',name='Computing')
        self.foreign_dep=Department.objects.create(institution=self.j,code='QA',name='Other')
        self.root='/api/institutions/hr-a/'
        self.client.force_login(self.users['admin'])
        self.machine=Client(enforce_csrf_checks=True)
        self.today=timezone.localdate()
    def post(self,path,data,status=201):
        r=self.client.post(self.root+path,data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def employee(self,role,code):
        return self.post('hr/employee/',{'code':code,'name':'Employee '+code,'designation':'Staff','department':self.dep.pk,'membership':self.members[role].pk,'category':'teaching','joined_on':str(self.today-timedelta(days=10))})['id']
    def event(self,token,external,subject,event_type='in',occurred=None,status=201):
        r=self.machine.post('/api/connect/events/',{'external_id':external,'subject_ref':subject,'event_type':event_type,'occurred_at':(occurred or timezone.now()).isoformat()},content_type='application/json',HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def test_employee_device_projection_and_scope(self):
        e=self.employee('faculty','E1')
        self.employee('finance','E2')
        source=self.post('connect/sources/',{'name':'Employee gate','purpose':'employee'})
        self.assertEqual(self.event(source['token'],'old','opaque-1')['status'],'staged')
        self.post('hr/map/',{'employee':e,'source':source['id'],'subject_ref':'opaque-1'})
        self.post('hr/map/',{'employee':e,'source':source['id'],'subject_ref':'opaque-1'},400)
        occurred=timezone.now()
        self.assertEqual(self.event(source['token'],'new','opaque-1',occurred=occurred)['status'],'employee_punch')
        self.assertEqual(self.event(source['token'],'new','opaque-1',occurred=occurred,status=200)['status'],'employee_punch')
        self.assertEqual(self.event(source['token'],'unknown','opaque-2')['status'],'staged')
        self.assertEqual(self.event(source['token'],'nondirectional','opaque-1',event_type='attendance')['status'],'staged')
        self.assertEqual(self.event(source['token'],'backdated','opaque-1',occurred=occurred-timedelta(days=1))['status'],'staged')
        self.assertEqual(EmployeePunch.objects.count(),1)
        self.assertEqual(IntegrationEvent.objects.count(),5)
        self.client.force_login(self.users['faculty'])
        d=self.client.get(self.root+'hr/').json()
        self.assertEqual(len(d['employees']),1)
        self.assertEqual(len(d['punches']),1)
        self.assertEqual(d['punches'][0]['employee__code'],'E1')
        self.assertNotIn('mappings',d)
        self.client.force_login(self.users['finance'])
        self.assertEqual(self.client.get(self.root+'hr/').json()['punches'],[])
        self.client.force_login(self.users['foreign'])
        self.assertEqual(self.client.get(self.root+'hr/').status_code,403)
        self.client.force_login(self.users['student'])
        self.assertEqual(self.client.get(self.root+'hr/').status_code,403)
    def test_employee_leave_and_approval(self):
        self.employee('faculty','E1')
        self.employee('finance','E2')
        self.employee('principal','P1')
        self.post('hr/employee/',{'code':'BAD','name':'Bad','designation':'Staff','department':self.foreign_dep.pk,'category':'teaching','joined_on':str(self.today)},404)
        self.client.force_login(self.users['faculty'])
        payload={'category':'Casual','starts':str(self.today),'ends':str(self.today+timedelta(days=1)),'reason':'Synthetic request'}
        leave=self.post('hr/leave/',payload)['id']
        self.post('hr/leave/',payload,400)
        self.post('hr/review/',{'leave':leave,'decision':'approved'},403)
        self.client.force_login(self.users['finance'])
        self.assertEqual(self.client.get(self.root+'hr/').json()['leaves'],[])
        self.post('hr/review/',{'leave':leave,'decision':'withdrawn'},403)
        self.client.force_login(self.users['principal'])
        self.post('hr/review/',{'leave':leave,'decision':'approved'})
        self.post('hr/review/',{'leave':leave,'decision':'rejected','note':'Late change'},400)
        own=self.post('hr/leave/',payload)['id']
        self.post('hr/review/',{'leave':own,'decision':'approved'},403)
        self.post('hr/review/',{'leave':own,'decision':'withdrawn'})
        self.client.force_login(self.users['faculty'])
        d=self.client.get(self.root+'hr/').json()
        self.assertEqual(len(d['leaves']),1)
        self.assertEqual(d['leaves'][0]['status'],'approved')
        self.assertEqual(EmployeeLeave.objects.count(),2)
