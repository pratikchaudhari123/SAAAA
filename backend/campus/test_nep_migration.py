from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,CreditRecognition
class NepMigrationTests(TestCase):
    def test_mapped_import_and_recognition(self):
        i=Institution.objects.create(name='A',slug='nep-a')
        users={}
        for role in ['admin','principal','student']:
            u=get_user_model().objects.create_user(username='nep-'+role);users[role]=u;Membership.objects.create(institution=i,user=u,role=role)
        root='/api/institutions/nep-a/'
        def login(role):self.client.force_login(users[role])
        def post(path,data,status=201):
            r=self.client.post(root+path+'/',data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content);return r.json()
        login('admin')
        raw='Roll,FullName,Mail,Degree,Level,Other\nQ1,QA,qa@example.invalid,Engineering,1,ignored\n'
        mapping={'student_id':'Roll','name':'FullName','email':'Mail','program':'Degree','year':'Level'}
        preview=post('connect/student-import',{'mode':'preview','csv':raw,'mapping':mapping},200)
        self.assertEqual(preview['new_rows'],1);self.assertFalse(Student.objects.exists())
        post('connect/student-import',{'mode':'apply','csv':raw,'mapping':mapping,'file_digest':preview['file_digest']})
        s=Student.objects.get();self.assertEqual(s.status,'Pending');s.status='Active';s.portal_user=users['student'];s.save()
        dep=Department.objects.create(institution=i,code='CS',name='CS')
        p=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=20)
        c=AcademicCourse.objects.create(program=p,code='C1',name='Course',semester=1,credits=3)
        login('student')
        payload={'course':c.pk,'source_institution':'Synthetic provider','source_reference':'QA1','credits':2}
        row=post('nep/apply',payload)['id']
        post('nep/apply',payload,400)
        row2=post('nep/apply',{**payload,'source_reference':'QA2'})['id']
        login('principal')
        post('nep/review',{'id':row,'decision':'approved','note':'Verified synthetic reference'})
        post('nep/review',{'id':row2,'decision':'approved','note':'Would exceed course maximum'},400)
        self.assertEqual(CreditRecognition.objects.filter(status='approved').count(),1)
