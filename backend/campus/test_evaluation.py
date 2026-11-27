from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,CourseEnrollment,CourseExam,ExamApplication,BookEvaluation,QuestionScore)

class EvaluationTests(TestCase):
    def setUp(self):
        i=Institution.objects.create(name='Evaluation A',slug='eval-a')
        j=Institution.objects.create(name='Evaluation B',slug='eval-b')
        self.users={}
        self.members={}
        for role in ('coe','faculty','other','student','foreign'):
            u=get_user_model().objects.create_user(username='eval-'+role,password='test-only')
            self.users[role]=u
            self.members[role]=Membership.objects.create(institution=j if role=='foreign' else i,user=u,role='faculty' if role in ('other','foreign') else role)
        dep=Department.objects.create(institution=i,code='CSE',name='Computing')
        prog=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=60)
        course=AcademicCourse.objects.create(program=prog,code='CS101',name='Programming',semester=1,credits=3)
        today=timezone.localdate()
        period=AcademicPeriod.objects.create(institution=i,code='QA',starts=today-timedelta(days=2),ends=today+timedelta(days=2))
        offering=CourseOffering.objects.create(course=course,period=period,batch='A',faculty=self.members['faculty'])
        s=Student.objects.create(institution=i,student_id='S1',name='Private Candidate',email='s1@example.invalid',program='Engineering',year=1,status='Active',portal_user=self.users['student'])
        e=CourseEnrollment.objects.create(offering=offering,student=s)
        self.exam=CourseExam.objects.create(offering=offering,title='QA Exam',kind='regular',day=today,maximum=100,passing=40,min_attendance=0)
        self.app=ExamApplication.objects.create(exam=self.exam,enrollment=e)
        self.root='/api/institutions/eval-a/'
        self.client.force_login(self.users['coe'])
    def post(self,path,data,status=201):
        r=self.client.post(self.root+path,data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def question(self,code,maximum,status=201):
        return self.post('evaluation/question/',{'exam':self.exam.pk,'code':code,'maximum':maximum,'course_outcome':'CO1','bloom_level':3},status)
    def test_question_evaluation_lifecycle(self):
        q1=self.question('Q1',40)['id']
        self.question('Q2',70,400)
        self.post('examination/state/',{'exam':self.exam.pk,'status':'closed'},400)
        q2=self.question('Q2',60)['id']
        self.post('examination/state/',{'exam':self.exam.pk,'status':'closed'})
        self.question('Q3',1,400)
        self.post('examination/marks/',{'application':self.app.pk,'marks':90},400)
        self.post('evaluation/assign/',{'application':self.app.pk,'examiner':self.members['foreign'].pk},404)
        b=self.post('evaluation/assign/',{'application':self.app.pk,'examiner':self.members['faculty'].pk})['id']
        self.post('evaluation/assign/',{'application':self.app.pk,'examiner':self.members['faculty'].pk},400)
        self.post('examination/state/',{'exam':self.exam.pk,'status':'published'},400)
        self.client.force_login(self.users['other'])
        self.assertEqual(self.client.get(self.root+'evaluation/').json()['books'],[])
        self.post('evaluation/score/',{'evaluation':b,'question':q1,'marks':10},404)
        self.client.force_login(self.users['faculty'])
        data=self.client.get(self.root+'evaluation/').json()
        self.assertEqual(len(data['books']),1)
        self.assertNotIn('applications',data)
        self.assertNotIn('Private Candidate',str(data))
        self.post('evaluation/score/',{'evaluation':b,'question':q1,'marks':41},400)
        self.post('evaluation/score/',{'evaluation':b,'question':q1,'marks':32})
        self.post('evaluation/submit/',{'evaluation':b},400)
        self.post('evaluation/score/',{'evaluation':b,'question':q2,'marks':50})
        self.post('evaluation/submit/',{'evaluation':b})
        self.post('evaluation/score/',{'evaluation':b,'question':q1,'marks':20},400)
        self.post('evaluation/review/',{'evaluation':b,'decision':'approved'},403)
        self.client.force_login(self.users['coe'])
        self.post('evaluation/review/',{'evaluation':b,'decision':'returned'},400)
        self.post('evaluation/review/',{'evaluation':b,'decision':'returned','note':'Recheck Q2'})
        self.client.force_login(self.users['faculty'])
        self.post('evaluation/score/',{'evaluation':b,'question':q2,'marks':52})
        self.post('evaluation/submit/',{'evaluation':b})
        self.client.force_login(self.users['coe'])
        self.post('evaluation/review/',{'evaluation':b,'decision':'approved'})
        self.app.refresh_from_db()
        self.assertEqual(self.app.marks,84)
        self.assertEqual(QuestionScore.objects.count(),2)
        self.client.force_login(self.users['student'])
        self.assertEqual(self.client.get(self.root+'evaluation/').status_code,403)
        self.assertIsNone(self.client.get(self.root+'examination/').json()['applications'][0]['marks'])
        self.client.force_login(self.users['coe'])
        self.post('examination/state/',{'exam':self.exam.pk,'status':'published'})
        self.client.force_login(self.users['student'])
        result=self.client.get(self.root+'examination/').json()['applications'][0]
        self.assertEqual((result['marks'],result['result']),(84,'Pass'))
        self.client.force_login(self.users['faculty'])
        self.post('evaluation/score/',{'evaluation':b,'question':q1,'marks':1},400)
        self.assertEqual(BookEvaluation.objects.get(pk=b).status,'approved')
