import base64,io,zipfile
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Institution,Membership,Department,AcademicProgram,AcademicCourse,AcademicPeriod,CourseOffering,Student,CourseEnrollment,LearningAttachment
class AttachmentTests(TestCase):
    def test_upload_validation_and_private_enrollment_scope(self):
        i=Institution.objects.create(name='A',slug='file-a')
        j=Institution.objects.create(name='B',slug='file-b')
        users={};members={}
        for name,role in [('faculty','faculty'),('other','faculty'),('student','student'),('outsider','student'),('foreign','admin')]:
            u=get_user_model().objects.create_user(username='file-'+name);users[name]=u
            members[name]=Membership.objects.create(institution=j if name=='foreign' else i,user=u,role=role)
        dep=Department.objects.create(institution=i,code='CS',name='Computing')
        p=AcademicProgram.objects.create(department=dep,code='BE',name='Engineering',duration_years=4,intake=20)
        c=AcademicCourse.objects.create(program=p,code='CS1',name='Programming',semester=1,credits=3)
        today=timezone.localdate()
        period=AcademicPeriod.objects.create(institution=i,code='QA',starts=today,ends=today+timedelta(days=30))
        o=CourseOffering.objects.create(course=c,period=period,faculty=members['faculty'],batch='A')
        for name in ['student','outsider']:
            s=Student.objects.create(institution=i,student_id=name,name=name,email=name+'@example.invalid',program='Engineering',year=1,status='Active',portal_user=users[name])
            if name=='student': CourseEnrollment.objects.create(offering=o,student=s)
        root='/api/institutions/file-a/learning/'
        def login(name): self.client.force_login(users[name])
        def post(data,status=201):
            r=self.client.post(root+'attachment/',data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content)
            return r.json()
        # Small synthetic format fixture, not a claim of complete PDF parsing.
        pdf=b'%PDF-1.4\nsynthetic format fixture\n%%EOF'
        payload={'offering':o.pk,'title':'Notes','filename':'unit-1.pdf','content':base64.b64encode(pdf).decode()}
        login('faculty')
        post({**payload,'filename':'bad.exe'},400)
        post({**payload,'content':'invalid'},400)
        post({**payload,'content':base64.b64encode(b'not a pdf').decode()},400)
        post(payload)
        row=LearningAttachment.objects.get()
        url=root+'attachments/'+str(row.pk)+'/'
        r=self.client.get(url)
        self.assertEqual(r.status_code,200)
        self.assertEqual(b''.join(r.streaming_content),pdf)
        self.assertIn('attachment',r['Content-Disposition'])
        self.assertEqual(r['X-Content-Type-Options'],'nosniff')
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('[Content_Types].xml','<Types/>')
            z.writestr('ppt/presentation.xml','<presentation/>')
        post({**payload,'filename':'lecture.pptx','content':base64.b64encode(buf.getvalue()).decode()})
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('[Content_Types].xml','<Types/>')
            z.writestr('ppt/presentation.xml','<presentation/>')
            z.writestr('ppt/vbaProject.bin','synthetic')
        post({**payload,'filename':'unsafe.pptx','content':base64.b64encode(buf.getvalue()).decode()},400)
        login('student')
        self.assertEqual(len(self.client.get(root).json()['attachments']),2)
        self.assertEqual(self.client.get(url).status_code,200)
        post(payload,403)
        for name in ['other','outsider']:
            login(name)
            self.assertEqual(self.client.get(root).json()['attachments'],[])
            self.assertEqual(self.client.get(url).status_code,404)
        login('foreign')
        self.assertEqual(self.client.get(url).status_code,403)
