from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,CourseEnrollment,Classroom,LectureSession,LectureTeachingPlan
class TimetableTests(TestCase):
    def test_calendar_recurring_atomic_conflicts_and_scope(self):
        i=Institution.objects.create(name='A',slug='schedule-a')
        j=Institution.objects.create(name='B',slug='schedule-b')
        users={};members={}
        for name,role in [('admin','admin'),('teacher','faculty'),('other','faculty'),('student','student'),('foreign','admin')]:
            u=get_user_model().objects.create_user(username='schedule-'+name);users[name]=u
            members[name]=Membership.objects.create(institution=j if name=='foreign' else i,user=u,role=role)
        dep=Department.objects.create(institution=i,code='CS',name='Computing')
        p=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=20)
        c=AcademicCourse.objects.create(program=p,code='CS1',name='Programming',semester=1,credits=3)
        c2=AcademicCourse.objects.create(program=p,code='CS2',name='Networks',semester=1,credits=3)
        day=timezone.localdate()+timedelta(days=2)
        period=AcademicPeriod.objects.create(institution=i,code='QA',starts=day,ends=day+timedelta(days=30))
        o=CourseOffering.objects.create(course=c,period=period,faculty=members['teacher'],batch='A')
        o2=CourseOffering.objects.create(course=c2,period=period,faculty=members['other'],batch='B')
        s=Student.objects.create(institution=i,student_id='QA',name='Synthetic',email='qa@example.invalid',program='Engineering',year=1,status='Active',portal_user=users['student'])
        CourseEnrollment.objects.create(offering=o,student=s)
        room=Classroom.objects.create(institution=i,code='R1',capacity=20)
        other_room=Classroom.objects.create(institution=j,code='Foreign',capacity=20)
        root='/api/institutions/schedule-a/'
        def login(name): self.client.force_login(users[name])
        def post(path,data,status=201):
            r=self.client.post(root+path+'/',data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content)
            return r.json()
        login('admin')
        holiday=day+timedelta(days=1)
        post('timetable/calendar',{'period':period.pk,'day':str(holiday),'title':'Synthetic holiday','kind':'holiday'})
        payload={'offering':o.pk,'room':room.pk,'first':str(day),'last':str(day+timedelta(days=2)),'weekdays':list(range(7)),'starts':'09:00','ends':'10:00'}
        preview=post('timetable/preview',payload,200)
        self.assertEqual(len(preview['planned']),2)
        self.assertEqual(preview['skipped_holidays'],[str(holiday)])
        self.assertEqual(LectureSession.objects.count(),0)
        post('timetable/generate',{**payload,'room':other_room.pk},404)
        self.assertEqual(post('timetable/generate',payload)['created'],2)
        self.assertEqual(post('timetable/generate',payload)['created'],0)
        self.assertEqual(LectureSession.objects.count(),2)
        self.assertEqual(len(post('timetable/preview',{**payload,'offering':o2.pk},200)['conflicts']),2)
        post('timetable/generate',{**payload,'offering':o2.pk},400)
        self.assertEqual(LectureSession.objects.count(),2)
        post('academic-engine/session',{'offering':o.pk,'room':room.pk,'starts':str(holiday)+'T09:00:00+05:30','ends':str(holiday)+'T10:00:00+05:30'},400)
        session=LectureSession.objects.filter(offering=o).order_by('starts').first()
        post('timetable/calendar',{'period':period.pk,'day':str(day),'title':'Blocked','kind':'holiday'},400)
        login('teacher')
        post('timetable/plan',{'session':session.pk,'topics':'Unit 1'})
        post('timetable/plan',{'session':session.pk,'topics':'Unit 1','delivery_note':'Not yet delivered'},400)
        login('other')
        post('timetable/plan',{'session':session.pk,'topics':'Unauthorized'},404)
        login('admin')
        move={'session':session.pk,'room':room.pk,'starts':str(holiday)+'T09:00:00+05:30','ends':str(holiday)+'T10:00:00+05:30','reason':'Makeup'}
        post('timetable/move',move,400)
        moved=day+timedelta(days=3)
        post('timetable/move',{**move,'starts':str(moved)+'T09:00:00+05:30','ends':str(moved)+'T10:00:00+05:30'})
        self.assertTrue(LectureTeachingPlan.objects.filter(session=session,topics='Unit 1').exists())
        login('student')
        data=self.client.get(root+'timetable/').json()
        self.assertEqual(len(data['sessions']),2)
        self.assertNotIn('rooms',data)
        post('timetable/generate',payload,403)
        login('foreign')
        self.assertEqual(self.client.get(root+'timetable/').status_code,403)
