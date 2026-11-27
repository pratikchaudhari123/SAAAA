from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,Department,AcademicProgram,AdmissionApplication
class RegistrationTests(TestCase):
    def test_invited_application_and_approval(self):
        i=Institution.objects.create(name='A',slug='reg-a')
        j=Institution.objects.create(name='B',slug='reg-b')
        users={}
        for name,role in [('admin','admin'),('admissions','admissions'),('candidate','applicant'),('other','applicant'),('foreign','applicant')]:
            u=get_user_model().objects.create_user(username='reg-'+name)
            users[name]=u
            Membership.objects.create(institution=j if name=='foreign' else i,user=u,role=role)
        dep=Department.objects.create(institution=i,code='CS',name='Computing')
        p=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=10)
        root='/api/institutions/reg-a/registration/'
        def login(name): self.client.force_login(users[name])
        def post(action,data,status=201):
            r=self.client.post(root+action+'/',data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content)
            return r.json()
        today=timezone.localdate()
        login('admin')
        rule=post('rule',{'program':p.pk,'code':'QA','opens':str(today),'closes':str(today+timedelta(days=2)),'qualification':'HSC','minimum_percent':'60','seats':1,'estimated_fee':'5000','required_documents':['hsc']})['id']
        login('candidate')
        self.assertEqual(self.client.get('/api/institutions/reg-a/students/').status_code,403)
        self.assertEqual(self.client.get('/api/institutions/reg-a/communications/').status_code,403)
        post('draft',{'rule':rule})
        self.assertEqual(self.client.get(root).json()['applications'][0]['status'],'draft')
        post('submit',{'confirmed':True},400)
        post('draft',{'rule':rule,'name':'Candidate','email':'candidate@example.invalid','qualification':'HSC','percent':'85'})
        post('submit',{'confirmed':True},400)
        post('document',{'kind':'hsc','image':'invalid'},400)
        import io,base64
        from PIL import Image
        b=io.BytesIO();Image.new('RGB',(32,48),'white').save(b,format='PNG')
        image=base64.b64encode(b.getvalue()).decode()
        doc=post('document',{'kind':'hsc','image':image})['id']
        self.assertEqual(self.client.get(root+'documents/'+str(doc)+'/').status_code,200)
        app=post('submit',{'confirmed':True})['id']
        post('draft',{'rule':rule},400)
        login('other')
        self.assertEqual(self.client.get(root).json()['applications'],[])
        self.assertEqual(self.client.get(root+'documents/'+str(doc)+'/').status_code,404)
        login('foreign')
        self.assertEqual(self.client.get(root).status_code,403)
        login('admissions')
        post('review',{'id':app,'decision':'approved','note':'QA reference','verified':False},400)
        post('review',{'id':app,'decision':'approved','note':'QA reference','verified':True})
        s=Student.objects.get(portal_user=users['candidate'])
        self.assertEqual(s.status,'Active')
        self.assertEqual(Membership.objects.get(user=users['candidate']).role,'student')
        self.assertEqual(AdmissionApplication.objects.get(pk=app).student,s)
        login('candidate')
        self.assertEqual(self.client.get(root).status_code,403)
        self.assertEqual(self.client.get('/api/institutions/reg-a/my-campus/').json()['profile']['student_id'],s.student_id)
