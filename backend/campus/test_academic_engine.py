from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,CourseEnrollment,LectureSession,SessionAttendance,CourseExam,ExamApplication,AuditEvent)

class AcademicEngineTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='Campus A',slug='academic-a')
        self.other=Institution.objects.create(name='Campus B',slug='academic-b')
        self.users={}
        self.members={}
        for role in ('admin','faculty','student','coe','viewer'):
            u=get_user_model().objects.create_user(username='academic-'+role,password='test-only')
            self.users[role]=u
            self.members[role]=Membership.objects.create(institution=self.i,user=u,role=role)
        self.second_faculty=get_user_model().objects.create_user(username='other-faculty')
        self.second_member=Membership.objects.create(institution=self.i,user=self.second_faculty,role='faculty')
        self.client.force_login(self.users['admin'])
        self.root='/api/institutions/academic-a/'
        dep=Department.objects.create(institution=self.i,code='CSE',name='Computing')
        prog=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=60)
        self.course=AcademicCourse.objects.create(program=prog,code='CS101',name='Programming',semester=1,credits=3)
        self.today=timezone.localdate()
        self.period=AcademicPeriod.objects.create(institution=self.i,code='QA',starts=self.today-timedelta(days=10),ends=self.today+timedelta(days=10))
        self.student=Student.objects.create(institution=self.i,portal_user=self.users['student'],student_id='A1',name='Student A',email='a@example.invalid',program='Engineering',year=1,status='Active')
        self.student2=Student.objects.create(institution=self.i,student_id='A2',name='Student B',email='b@example.invalid',program='Engineering',year=1,status='Active')
        self.foreign=AcademicPeriod.objects.create(institution=self.other,code='OTHER',starts=self.period.starts,ends=self.period.ends)
    def post(self,path,data,status=201):
        r=self.client.post(self.root+path,data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def setup_offering(self):
        room=self.post('academic-engine/room/',{'code':'R101','capacity':10})['id']
        values={'course':self.course.pk,'period':self.period.pk,'faculty':self.members['faculty'].pk,'batch':'A'}
        self.post('academic-engine/offering/',{**values,'period':self.foreign.pk},404)
        offering=self.post('academic-engine/offering/',values)['id']
        self.post('academic-engine/offering/',values,400)
        enrollment=self.post('academic-engine/enrollment/',{'offering':offering,'student_id':'A1'})['id']
        other=self.post('academic-engine/enrollment/',{'offering':offering,'student_id':'A2'})['id']
        return room,offering,enrollment,other
    def session_payload(self,room,offering,offset=0):
        # Use local noon on yesterday for a reliably completed session.
        import datetime
        start=timezone.make_aware(datetime.datetime.combine(self.today-timedelta(days=1),datetime.time(10+offset)))
        return {'offering':offering,'room':room,'starts':start.isoformat(),'ends':(start+timedelta(minutes=45)).isoformat()}
    def test_scoped_sessions_and_conflicts(self):
        room,o,e,_=self.setup_offering()
        payload=self.session_payload(room,o)
        s=self.post('academic-engine/session/',payload)['id']
        self.post('academic-engine/session/',payload,400)
        t=self.post('academic-engine/session/',self.session_payload(room,o,1))['id']
        self.client.force_login(self.second_faculty)
        self.assertEqual(self.client.get(self.root+'academic-engine/').json()['offerings'],[])
        self.post('academic-engine/attendance/',{'session':s,'enrollment':e,'present':True},404)
        self.client.force_login(self.users['faculty'])
        self.post('academic-engine/attendance/',{'session':s,'enrollment':e,'present':True})
        self.post('academic-engine/attendance/',{'session':t,'enrollment':e,'present':False})
        self.assertEqual(SessionAttendance.objects.count(),2)
        self.post('academic-engine/attendance/',{'session':s,'enrollment':e,'present':False})
        self.assertEqual(SessionAttendance.objects.count(),2)
        self.client.force_login(self.users['student'])
        d=self.client.get(self.root+'academic-engine/').json()
        self.assertEqual(len(d['enrollments']),1)
        self.assertEqual(len(d['attendance']),2)
        self.post('academic-engine/attendance/',{'session':s,'enrollment':e,'present':True},403)
        self.assertEqual(self.client.get('/api/institutions/academic-b/academic-engine/').status_code,403)
    def test_exam_lifecycle_and_privacy(self):
        room,o,e,other=self.setup_offering()
        s=self.post('academic-engine/session/',self.session_payload(room,o))['id']
        self.post('academic-engine/attendance/',{'session':s,'enrollment':e,'present':True})
        self.post('academic-engine/attendance/',{'session':s,'enrollment':other,'present':False})
        self.client.force_login(self.users['coe'])
        config={'offering':o,'title':'Semester exam','kind':'regular','day':str(self.today),'maximum':100,'passing':40,'min_attendance':75}
        self.post('examination/create/',{**config,'passing':101},400)
        exam=self.post('examination/create/',config)['id']
        self.post('examination/apply/',{'exam':exam,'enrollment':other},400)
        self.client.force_login(self.users['student'])
        self.post('examination/apply/',{'exam':exam,'enrollment':other},404)
        app=self.post('examination/apply/',{'exam':exam,'enrollment':e})['id']
        self.post('examination/apply/',{'exam':exam,'enrollment':e},400)
        self.post('examination/marks/',{'application':app,'marks':80},403)
        self.client.force_login(self.users['coe'])
        self.post('examination/marks/',{'application':app,'marks':80},400)
        self.post('examination/state/',{'exam':exam,'status':'closed'})
        self.post('examination/state/',{'exam':exam,'status':'published'},400)
        self.post('examination/marks/',{'application':app,'marks':101},400)
        self.post('examination/marks/',{'application':app,'marks':80})
        self.client.force_login(self.users['student'])
        self.assertIsNone(self.client.get(self.root+'examination/').json()['applications'][0]['marks'])
        self.client.force_login(self.users['coe'])
        self.post('examination/state/',{'exam':exam,'status':'published'})
        self.post('examination/marks/',{'application':app,'marks':30},400)
        self.client.force_login(self.users['student'])
        data=self.client.get(self.root+'examination/').json()['applications']
        self.assertEqual(len(data),1)
        self.assertEqual((data[0]['marks'],data[0]['result']),(80,'Pass'))
        self.client.force_login(self.users['viewer'])
        self.assertEqual(self.client.get(self.root+'examination/').status_code,403)
        self.assertTrue(AuditEvent.objects.filter(action='exam.state').exists())
