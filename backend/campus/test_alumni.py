from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,AlumniRecord
class AlumniTests(TestCase):
    def test_certification_and_privacy(self):
        i=Institution.objects.create(name='A',slug='alu-a')
        j=Institution.objects.create(name='B',slug='alu-b')
        users={}
        for role in ['principal','student','admin','tpo','other']:
            u=get_user_model().objects.create_user(username='alu-'+role)
            Membership.objects.create(institution=j if role=='other' else i,user=u,role='student' if role=='other' else role)
            users[role]=u
        s=Student.objects.create(institution=i,portal_user=users['student'],student_id='S1',name='Synthetic',email='s@example.invalid',program='Engineering',year=4,status='Active')
        root='/api/institutions/alu-a/'
        def post(action,data,status=201):
            r=self.client.post(root+'alumni/'+action+'/',data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content)
            return r.json()
        payload={'student_id':'S1','graduation_day':str(timezone.localdate()),'approval_reference':'SYNTHETIC-APPROVAL','confirmed':True}
        self.client.force_login(users['admin'])
        post('graduate',payload,403)
        self.client.force_login(users['principal'])
        post('graduate',{**payload,'confirmed':False},400)
        post('graduate',payload)
        post('graduate',payload,400)
        s.refresh_from_db()
        self.assertEqual(s.status,'Graduated')
        self.assertEqual(Membership.objects.get(institution=i,user=users['student']).role,'alumni')
        self.client.force_login(users['student'])
        self.assertEqual(self.client.get(root+'students/').status_code,403)
        self.assertEqual(self.client.get(root+'careers/').status_code,403)
        post('profile',{'occupation':'employee','employer':'Synthetic employer','location':'Pune'})
        op=post('opportunity',{'kind':'training','title':'Workshop','description':'Synthetic workshop'})['id']
        self.client.force_login(users['tpo'])
        post('review',{'opportunity':op,'decision':'approved'})
        self.assertEqual(AlumniRecord.objects.get(student=s).location,'Pune')
        self.client.force_login(users['other'])
        self.assertEqual(self.client.get(root+'alumni/').status_code,403)
