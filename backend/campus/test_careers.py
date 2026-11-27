from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution, Membership, Student, RecruitmentApplication, AuditEvent

class CareerTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='Careers A',slug='career-a')
        self.j=Institution.objects.create(name='Careers B',slug='career-b')
        self.users={}
        for role in ('admin','tpo','tpo_assistant','company','company2','student','student2','principal','faculty','foreign'):
            u=get_user_model().objects.create_user(username='career-'+role,password='test-only')
            self.users[role]=u
            Membership.objects.create(institution=self.j if role=='foreign' else self.i,user=u,role={'company2':'company','student2':'student','foreign':'tpo'}.get(role,role))
        for role,year in [('student',4),('student2',1)]:
            Student.objects.create(institution=self.i,portal_user=self.users[role],student_id=role,name=role+' Example',email=role+'@example.invalid',program='Engineering',year=year,status='Active')
        self.root='/api/institutions/career-a/'
        self.today=timezone.localdate()
    def login(self,role):
        self.client.force_login(self.users[role])
    def post(self,path,payload,status=201):
        r=self.client.post(self.root+'careers/'+path+'/',payload,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def view(self):
        r=self.client.get(self.root+'careers/')
        self.assertEqual(r.status_code,200,r.content)
        return r.json()
    def company(self,role,name):
        self.login(role)
        return self.post('company',{'name':name,'contact_email':role+'@example.invalid'})['id']
    def drive(self,company,**extra):
        return {'company':company,'title':'Engineering internship','kind':'internship','program':'Engineering','min_year':3,'max_year':4,'deadline':str(self.today),'drive_day':str(self.today),'instructions':'Synthetic test',**extra}
    def test_placement_lifecycle_and_consent(self):
        c=self.company('company','Example Company')
        self.login('tpo')
        self.post('drive',self.drive(c),404)
        self.post('company-review',{'company':c,'decision':'approved'})
        self.post('drive',self.drive(c,min_year=5),400)
        d=self.post('drive',self.drive(c))['id']
        self.assertEqual(self.view()['eligible_counts'],[{'drive':d,'count':1}])
        eligible=self.client.get(self.root+'careers/drives/'+str(d)+'/eligible/').json()
        self.assertEqual([s['student_id'] for s in eligible],['student'])
        self.login('student2')
        self.assertEqual(self.view()['drives'],[])
        self.post('profile',{'skills':'SQL','summary':'Synthetic profile'})
        self.post('apply',{'drive':d,'consent':True},400)
        self.login('student')
        self.post('apply',{'drive':d,'consent':True},400)
        self.post('profile',{'skills':'Python','summary':'Synthetic profile'})
        self.post('apply',{'drive':d,'consent':False},400)
        a=self.post('apply',{'drive':d,'consent':True})['id']
        self.post('apply',{'drive':d,'consent':True},400)
        self.post('profile',{'skills':'Updated skill','summary':'Updated profile'})
        self.post('decision',{'application':a,'decision':'selected'},403)
        self.login('company')
        data=self.view()
        self.assertEqual(len(data['applications']),1)
        self.assertEqual(data['applications'][0]['skills'],'Python')
        self.assertNotIn('student__email',data['applications'][0])
        self.assertEqual(self.client.get(self.root+'students/').status_code,403)
        self.assertEqual(self.client.get(self.root+'careers/drives/'+str(d)+'/eligible/').status_code,403)
        self.login('tpo_assistant')
        self.post('decision',{'application':a,'decision':'shortlisted'},400)
        self.post('close',{'drive':d})
        self.post('decision',{'application':a,'decision':'selected'},400)
        self.post('decision',{'application':a,'decision':'shortlisted'})
        self.post('decision',{'application':a,'decision':'selected'})
        self.assertEqual(self.view()['internship_count'],1)
        self.login('student')
        self.assertEqual(self.view()['applications'][0]['status'],'selected')
        self.post('decision',{'application':a,'decision':'withdrawn'},400)
        self.assertEqual(RecruitmentApplication.objects.count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='career.decision').exists())
    def test_company_isolation_withdrawal_and_role_boundaries(self):
        c=self.company('company','First Company')
        other=self.company('company2','Second Company')
        self.login('tpo_assistant')
        self.post('company-review',{'company':c,'decision':'approved'},403)
        self.login('admin')
        self.post('company-review',{'company':c,'decision':'approved'})
        self.post('company-review',{'company':other,'decision':'approved'})
        d=self.post('drive',self.drive(c,min_year=1))['id']
        self.login('student')
        self.post('profile',{'skills':'SQL','summary':'Synthetic profile'})
        a=self.post('apply',{'drive':d,'consent':True})['id']
        self.login('student2')
        self.assertEqual(self.view()['applications'],[])
        self.post('decision',{'application':a,'decision':'withdrawn'},404)
        self.login('company2')
        self.assertEqual(self.view()['applications'],[])
        self.assertEqual(self.view()['drives'],[])
        self.post('decision',{'application':a,'decision':'selected'},403)
        self.assertEqual(self.client.get(self.root+'dashboard/').status_code,403)
        self.assertEqual(self.client.get(self.root+'operations/fees/').status_code,403)
        self.login('foreign')
        self.assertEqual(self.client.get(self.root+'careers/').status_code,403)
        self.login('principal')
        self.post('close',{'drive':d},403)
        self.login('faculty')
        self.assertEqual(self.client.get(self.root+'careers/').status_code,403)
        self.login('student')
        self.post('decision',{'application':a,'decision':'withdrawn'})
        self.login('company')
        self.assertEqual(self.view()['applications'],[])
