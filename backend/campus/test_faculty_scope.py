from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,CourseEnrollment,AttendanceEntry
class FacultyScopeTests(TestCase):
    def test_legacy_attendance_and_directory_scope(self):
        i=Institution.objects.create(name='Campus',slug='faculty-scope')
        u=get_user_model().objects.create_user(username='scope-faculty')
        m=Membership.objects.create(institution=i,user=u,role='faculty')
        dep=Department.objects.create(institution=i,code='CSE',name='Computing')
        p=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=60)
        c=AcademicCourse.objects.create(program=p,code='CS1',name='Programming',semester=1,credits=3)
        today=timezone.localdate()
        period=AcademicPeriod.objects.create(institution=i,code='QA',starts=today-timedelta(days=1),ends=today+timedelta(days=1))
        o=CourseOffering.objects.create(course=c,period=period,faculty=m,batch='A')
        s=Student.objects.create(institution=i,student_id='ASSIGNED',name='Assigned',email='a@example.invalid',program='Engineering',year=1,status='Active')
        t=Student.objects.create(institution=i,student_id='OTHER',name='Other',email='b@example.invalid',program='Engineering',year=1,status='Active')
        CourseEnrollment.objects.create(offering=o,student=s)
        AttendanceEntry.objects.create(student=t,day=today,course='CS1',present=True,recorded_by=u)
        AttendanceEntry.objects.create(student=s,day=today,course='OTHER',present=True,recorded_by=u)
        self.client.force_login(u)
        root='/api/institutions/faculty-scope/'
        self.assertEqual([r['student_id'] for r in self.client.get(root+'students/').json()],['ASSIGNED'])
        path=root+'operations/attendance/'
        self.assertEqual(self.client.get(path).json(),[])
        payload={'student_id':'ASSIGNED','day':str(today),'course':'CS1','present':True}
        for wrong in [{'student_id':'OTHER'},{'course':'OTHER'},{'day':str(today-timedelta(days=5))}]:
            self.assertEqual(self.client.post(path,{**payload,**wrong},content_type='application/json').status_code,403)
        self.assertEqual(self.client.post(path,payload,content_type='application/json').status_code,201)
        self.assertEqual(len(self.client.get(path).json()),1)
