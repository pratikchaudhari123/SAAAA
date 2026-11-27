from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,CourseEnrollment
class LearningTests(TestCase):
    def test_enrollment_scoped_learning(self):
        i=Institution.objects.create(name='A',slug='lms-a')
        users={};members={}
        for role in ['faculty','student','other','otherfaculty']:
            u=get_user_model().objects.create_user(username='lms-'+role)
            users[role]=u
            members[role]=Membership.objects.create(institution=i,user=u,role='faculty' if role=='otherfaculty' else 'student' if role=='other' else role)
        dep=Department.objects.create(institution=i,code='CS',name='Computing')
        prog=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=60)
        c=AcademicCourse.objects.create(program=prog,code='CS1',name='Programming',semester=1,credits=3)
        today=timezone.localdate()
        p=AcademicPeriod.objects.create(institution=i,code='QA',starts=today,ends=today+timedelta(days=10))
        o=CourseOffering.objects.create(course=c,period=p,batch='A',faculty=members['faculty'])
        for role in ['student','other']:
            s=Student.objects.create(institution=i,portal_user=users[role],student_id=role,name=role,email=role+'@example.invalid',program='Engineering',year=1,status='Active')
            if role=='student': CourseEnrollment.objects.create(offering=o,student=s)
        root='/api/institutions/lms-a/learning/'
        def post(action,data,status=201):
            r=self.client.post(root+action+'/',data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content)
            return r.json()
        self.client.force_login(users['faculty'])
        deadline=(timezone.now()+timedelta(days=1)).isoformat()
        post('resource',{'offering':o.pk,'title':'Notes','text':'Synthetic notes'})
        a=post('assignment',{'offering':o.pk,'title':'Task','instructions':'Answer','deadline':deadline,'maximum':10})['id']
        q=post('quiz',{'offering':o.pk,'title':'Quiz','deadline':deadline,'questions':[{'prompt':'2+2?','options':['3','4'],'correct':1}]})['id']
        self.client.force_login(users['other'])
        self.assertEqual(self.client.get(root).json()['resources'],[])
        post('submit',{'assignment':a,'answer':'Unauthorized'},404)
        self.client.force_login(users['student'])
        self.assertNotIn('correct',self.client.get(root).json()['quizzes'][0]['questions'][0])
        sub=post('submit',{'assignment':a,'answer':'Synthetic answer'})['id']
        post('submit',{'assignment':a,'answer':'Retry'},400)
        post('attempt',{'quiz':q,'answers':[1]})
        post('attempt',{'quiz':q,'answers':[0]},400)
        post('grade',{'submission':sub,'marks':10},403)
        self.client.force_login(users['otherfaculty'])
        post('grade',{'submission':sub,'marks':10},404)
        self.client.force_login(users['faculty'])
        post('grade',{'submission':sub,'marks':11},400)
        post('grade',{'submission':sub,'marks':8,'feedback':'Good work'})
        self.client.force_login(users['student'])
        d=self.client.get(root).json()
        self.assertEqual(d['attempts'][0]['score'],1)
        self.assertEqual(d['submissions'][0]['marks'],8)
