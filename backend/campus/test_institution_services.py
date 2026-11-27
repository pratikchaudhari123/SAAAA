from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (Institution,Membership,Student,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,CourseEnrollment,Classroom,CourseExam,ExamApplication,ExaminationSeat,SupportTicket,SupportTicketEvent,AccreditationEvidence)

class InstitutionServiceTests(TestCase):
    def setUp(self):
        self.i=Institution.objects.create(name='A',slug='service-a')
        self.j=Institution.objects.create(name='B',slug='service-b')
        self.users={};self.members={}
        for name,role in [('admin','admin'),('principal','principal'),('faculty','faculty'),('coe','coe'),('student','student'),('other','student'),('foreign','admin')]:
            u=get_user_model().objects.create_user(username='service-'+name);self.users[name]=u
            self.members[name]=Membership.objects.create(institution=self.j if name=='foreign' else self.i,user=u,role=role)
        dep=Department.objects.create(institution=self.i,code='CS',name='Computing')
        p=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=20)
        c=AcademicCourse.objects.create(program=p,code='CS1',name='Programming',semester=1,credits=3)
        self.day=timezone.localdate()+timedelta(days=3)
        self.period=AcademicPeriod.objects.create(institution=self.i,code='QA',starts=timezone.localdate(),ends=self.day+timedelta(days=30))
        self.offering=CourseOffering.objects.create(course=c,period=self.period,faculty=self.members['faculty'],batch='A')
        self.enrollments={}
        for name in ['student','other']:
            s=Student.objects.create(institution=self.i,student_id=name,name=name,email=name+'@example.invalid',program='Engineering',year=1,status='Active',portal_user=self.users[name])
            self.enrollments[name]=CourseEnrollment.objects.create(offering=self.offering,student=s)
        self.root='/api/institutions/service-a/'
    def login(self,name):self.client.force_login(self.users[name])
    def post(self,path,data,status=201):
        r=self.client.post(self.root+path+'/',data,content_type='application/json')
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def read(self,path,status=200):
        r=self.client.get(self.root+path)
        self.assertEqual(r.status_code,status,r.content)
        return r.json()
    def test_support_assignment_privacy_and_sla(self):
        self.login('student')
        t=self.post('support/create',{'title':'Synthetic request','description':'Test issue','category':'change'})['id']
        row=SupportTicket.objects.get(pk=t)
        self.assertGreater(row.resolution_due,row.response_due)
        self.post('support/resolve',{'id':t,'note':'No authority'},403)
        self.login('other')
        self.assertEqual(self.read('support/')['tickets'],[])
        self.post('support/comment',{'id':t,'note':'Not my ticket'},404)
        self.login('admin')
        self.post('support/assign',{'id':t,'assignee':self.members['foreign'].pk,'note':'Invalid'},404)
        self.post('support/assign',{'id':t,'assignee':self.members['faculty'].pk,'note':'Assign'})
        self.login('faculty')
        self.post('support/respond',{'id':t,'note':'Investigating'})
        self.post('support/resolve',{'id':t,'note':'Resolved'})
        self.login('student')
        self.post('support/close',{'id':t,'note':'Accepted'})
        self.assertEqual(self.read('support/')['tickets'][0]['status'],'closed')
        self.assertEqual(SupportTicketEvent.objects.filter(ticket_id=t).count(),5)
        self.login('foreign')
        self.read('support/',403)
    def test_accreditation_published_only_and_review(self):
        exam=CourseExam.objects.create(offering=self.offering,title='Published exam',kind='regular',day=self.day,maximum=100,passing=40,status='published')
        ExamApplication.objects.create(exam=exam,enrollment=self.enrollments['student'],marks=70)
        ExamApplication.objects.create(exam=exam,enrollment=self.enrollments['other'],marks=20)
        draft=CourseExam.objects.create(offering=self.offering,title='Unpublished exam',kind='regular',day=self.day,maximum=100,passing=40,status='closed')
        ExamApplication.objects.create(exam=draft,enrollment=self.enrollments['student'],marks=90)
        self.login('admin')
        r=self.read('accreditation/?period='+str(self.period.pk))
        self.assertEqual(r['results'][0]['attempts'],2)
        self.assertEqual(r['results'][0]['passed'],1)
        e=self.post('accreditation/evidence',{'period':self.period.pk,'framework':'NBA','criterion':'QA','title':'Synthetic evidence','description':'Test'})['id']
        self.post('accreditation/review',{'id':e,'confirmed':True},403)
        self.login('principal')
        self.post('accreditation/review',{'id':e,'confirmed':True})
        self.assertEqual(AccreditationEvidence.objects.get(pk=e).status,'reviewed')
        self.login('student')
        self.read('accreditation/',403)
        self.login('foreign')
        self.read('accreditation/',403)
    def test_seating_capacity_release_and_scope(self):
        exam=CourseExam.objects.create(offering=self.offering,title='QA exam',kind='regular',day=self.day,maximum=100,passing=40,status='closed')
        for e in self.enrollments.values():ExamApplication.objects.create(exam=exam,enrollment=e)
        room=Classroom.objects.create(institution=self.i,code='R1',capacity=1)
        room2=Classroom.objects.create(institution=self.i,code='R2',capacity=1)
        payload={'exam':exam.pk,'rooms':[room.pk],'starts':str(self.day)+'T09:00:00+05:30','ends':str(self.day)+'T10:00:00+05:30'}
        self.login('coe')
        self.post('exam-preparation/allocate',payload,400)
        self.assertEqual(ExaminationSeat.objects.count(),0)
        schedule=self.post('exam-preparation/allocate',{**payload,'rooms':[room.pk,room2.pk]})['id']
        self.assertEqual(ExaminationSeat.objects.count(),2)
        self.post('exam-preparation/allocate',{**payload,'rooms':[room.pk,room2.pk]},400)
        self.login('student')
        self.assertEqual(self.read('exam-preparation/')['seats'],[])
        self.post('exam-preparation/release',{'id':schedule,'confirmed':True},403)
        self.login('admin')
        self.post('academic-engine/session',{'offering':self.offering.pk,'room':room.pk,'starts':payload['starts'],'ends':payload['ends']},400)
        self.login('coe')
        self.post('exam-preparation/release',{'id':schedule,'confirmed':True})
        self.login('student')
        rows=self.read('exam-preparation/')['seats']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['application__enrollment__student__student_id'],'student')
        self.login('foreign')
        self.read('exam-preparation/',403)
