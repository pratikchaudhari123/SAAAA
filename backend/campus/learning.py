"""Enrollment-scoped LMS pilot: text/link resources, text assignments, single-attempt MCQs."""
import base64, binascii, hashlib, io, re, zipfile
from pathlib import PurePosixPath
from django.http import FileResponse
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, LearningResource, LearningAssignment, LearningSubmission, LearningQuiz, QuizAttempt, LearningAttachment
from .academic_engine import member, offerings, enrollments, get, parse, log

class Resource(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    text=serializers.CharField(max_length=20000,allow_blank=True,required=False,default='')
    url=serializers.URLField(allow_blank=True,required=False,default='')
    def validate(self,d):
        if not d['text'] and not d['url']: raise serializers.ValidationError('Provide notes or a link.')
        if d['url'] and not d['url'].startswith('https://'): raise serializers.ValidationError('Use HTTPS links.')
        return d
MAX_FILE=1500000
MAX_CAMPUS_FILES=100000000
MIMES={'pdf':'application/pdf','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'}

class AttachmentInput(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    filename=serializers.RegexField(regex=r'^[A-Za-z0-9][A-Za-z0-9 _().-]{0,148}
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    instructions=serializers.CharField(max_length=10000)
    deadline=serializers.DateTimeField()
    maximum=serializers.IntegerField(min_value=1,max_value=1000)
class Submission(serializers.Serializer):
    assignment=serializers.IntegerField(min_value=1)
    answer=serializers.CharField(max_length=20000)
class Grade(serializers.Serializer):
    submission=serializers.IntegerField(min_value=1)
    marks=serializers.IntegerField(min_value=0,max_value=1000)
    feedback=serializers.CharField(max_length=1000,allow_blank=True,required=False,default='')
class Question(serializers.Serializer):
    prompt=serializers.CharField(max_length=1000)
    options=serializers.ListField(child=serializers.CharField(max_length=500),min_length=2,max_length=6)
    correct=serializers.IntegerField(min_value=0,max_value=5)
    def validate(self,d):
        if d['correct']>=len(d['options']) or len(set(d['options']))!=len(d['options']): raise serializers.ValidationError('Select one valid answer and distinct options.')
        return d
class Quiz(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    deadline=serializers.DateTimeField()
    questions=Question(many=True,min_length=1,max_length=30)
class Attempt(serializers.Serializer):
    quiz=serializers.IntegerField(min_value=1)
    answers=serializers.ListField(child=serializers.IntegerField(min_value=0,max_value=5),min_length=1,max_length=30)

def roster(m):
    q=enrollments(m)
    return q.filter(student__status='Active') if m.role=='student' else q
def courses(m):
    q=offerings(m)
    return q.filter(enrollments__in=roster(m)).distinct() if m.role=='student' else q

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','faculty','student'])
    o=courses(m)
    es=roster(m)
    submissions=LearningSubmission.objects.filter(assignment__offering__in=o,enrollment__in=es)
    attempts=QuizAttempt.objects.filter(quiz__offering__in=o,enrollment__in=es)
    quizzes=list(LearningQuiz.objects.filter(offering__in=o).values('id','offering_id','title','deadline','questions'))
    # Answer keys are never included in the student response.
    if m.role=='student':
        for q in quizzes: q['questions']=[{'prompt':x['prompt'],'options':x['options']} for x in q['questions']]
    fields=['id','assignment_id','answer','marks','feedback','submitted_at']
    if m.role!='student': fields+=['enrollment__student__student_id','enrollment__student__name']
    data={'offerings':list(o.values('id','course__code','course__name','batch')),
          'resources':list(LearningResource.objects.filter(offering__in=o).order_by('-pk').values('id','offering_id','title','text','url')),
          'attachments':list(LearningAttachment.objects.filter(resource__offering__in=o).order_by('-pk').values('id','resource_id','filename','size','sha256','content_type')),
          'assignments':list(LearningAssignment.objects.filter(offering__in=o).order_by('-pk').values('id','offering_id','title','instructions','deadline','maximum')),
          'submissions':list(submissions.values(*fields)),
          'quizzes':quizzes,
          'attempts':list(attempts.values('quiz_id','score',*(['enrollment__student__student_id'] if m.role!='student' else [])))}
    response=Response(data); response['Cache-Control']='private, no-store'
    return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','faculty','student'])
    schemas={'attachment':AttachmentInput,'resource':Resource,'assignment':Assignment,'submit':Submission,'grade':Grade,'quiz':Quiz,'attempt':Attempt}
    if action not in schemas: raise NotFound()
    if (action in ('submit','attempt'))!=(m.role=='student'): raise PermissionDenied()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            o=courses(m)
            es=roster(m)
            if action=='attachment':
                offering=get(o,d['offering'])
                raw,kind=checked_file(d['filename'],d['content'])
                used=LearningAttachment.objects.filter(resource__offering__period__institution=m.institution).aggregate(total=Sum('size'))['total'] or 0
                if used+len(raw)>MAX_CAMPUS_FILES: raise ValidationError('Evaluation attachment quota reached; storage configuration required.')
                resource=LearningResource.objects.create(offering=offering,title=d['title'])
                row=LearningAttachment.objects.create(resource=resource,filename=d['filename'],content_type=kind,content=raw,size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),uploaded_by=m.user)
            elif action in ('resource','assignment','quiz'):
                offering=get(o,d.pop('offering'))
                if 'deadline' in d and d['deadline']<=timezone.now(): raise ValidationError('Deadline must be in the future.')
                model={'resource':LearningResource,'assignment':LearningAssignment,'quiz':LearningQuiz}[action]
                row=model.objects.create(offering=offering,**d)
            elif action=='submit':
                assignment=get(LearningAssignment.objects.filter(offering__in=o),d['assignment'])
                if assignment.deadline<timezone.now(): raise ValidationError('Submission deadline has passed.')
                enrollment=es.filter(offering=assignment.offering).first()
                if not enrollment: raise PermissionDenied()
                row=LearningSubmission.objects.create(assignment=assignment,enrollment=enrollment,answer=d['answer'])
            elif action=='grade':
                row=get(LearningSubmission.objects.filter(assignment__offering__in=o,enrollment__in=es),d['submission'])
                if row.marks is not None: raise ValidationError('Already graded; corrections require a separate review workflow.')
                if d['marks']>row.assignment.maximum: raise ValidationError('Marks exceed assignment maximum.')
                row.marks=d['marks'];row.feedback=d['feedback'];row.save(update_fields=['marks','feedback'])
            else:
                quiz=get(LearningQuiz.objects.filter(offering__in=o),d['quiz'])
                if quiz.deadline<timezone.now(): raise ValidationError('Quiz deadline has passed.')
                enrollment=es.filter(offering=quiz.offering).first()
                if not enrollment: raise PermissionDenied()
                answers=d['answers']
                if len(answers)!=len(quiz.questions) or any(a>=len(q['options']) for a,q in zip(answers,quiz.questions)): raise ValidationError('Answer each question with a valid option.')
                score=sum(a==q['correct'] for a,q in zip(answers,quiz.questions))
                row=QuizAttempt.objects.create(quiz=quiz,enrollment=enrollment,answers=answers,score=score)
            log(m,'learning.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid learning record.')
    return Response({'id':row.pk},status=201)
,max_length=150)
    content=serializers.CharField(max_length=2000000)

def checked_file(filename,encoded):
    extension=filename.rsplit('.',1)[-1].lower()
    if extension not in MIMES: raise ValidationError('Only PDF and PPTX attachments are supported.')
    try: raw=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error): raise ValidationError('Invalid attachment encoding.')
    if not raw or len(raw)>MAX_FILE: raise ValidationError('Attachment exceeds the 1.5 MB evaluation limit.')
    if extension=='pdf':
        if not re.match(br'^%PDF-[12]\.\d',raw[:16]) or not raw.rstrip().endswith(b'%%EOF'):
            raise ValidationError('Invalid PDF header or end marker.')
        # This is a format gate, not a malware scanner.
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries=archive.infolist()
                names={e.filename for e in entries}
                if len(entries)>500 or len(names)!=len(entries) or sum(e.file_size for e in entries)>16000000:
                    raise ValidationError('Presentation archive exceeds allowed complexity.')
                if not {'[Content_Types].xml','ppt/presentation.xml'}.issubset(names):
                    raise ValidationError('Presentation package structure is missing.')
                for e in entries:
                    name=e.filename.lower()
                    if e.flag_bits&1 or name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts or 'vbaproject' in name or '/embeddings/' in name or '/activex/' in name:
                        raise ValidationError('Encrypted, unsafe-path, macro or embedded-object presentations are not allowed.')
                if archive.testzip() is not None: raise ValidationError('Corrupt presentation package.')
        except (zipfile.BadZipFile,RuntimeError,NotImplementedError,ValueError,OSError): raise ValidationError('Invalid presentation package.')
    return raw,MIMES[extension]

@api_view(['GET'])
def download(request,slug,pk):
    m=member(request,slug,['admin','faculty','student'])
    a=get(LearningAttachment.objects.filter(resource__offering__in=courses(m)),pk)
    response=FileResponse(io.BytesIO(bytes(a.content)),as_attachment=True,filename=a.filename,content_type=a.content_type)
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response

class Assignment(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    instructions=serializers.CharField(max_length=10000)
    deadline=serializers.DateTimeField()
    maximum=serializers.IntegerField(min_value=1,max_value=1000)
class Submission(serializers.Serializer):
    assignment=serializers.IntegerField(min_value=1)
    answer=serializers.CharField(max_length=20000)
class Grade(serializers.Serializer):
    submission=serializers.IntegerField(min_value=1)
    marks=serializers.IntegerField(min_value=0,max_value=1000)
    feedback=serializers.CharField(max_length=1000,allow_blank=True,required=False,default='')
class Question(serializers.Serializer):
    prompt=serializers.CharField(max_length=1000)
    options=serializers.ListField(child=serializers.CharField(max_length=500),min_length=2,max_length=6)
    correct=serializers.IntegerField(min_value=0,max_value=5)
    def validate(self,d):
        if d['correct']>=len(d['options']) or len(set(d['options']))!=len(d['options']): raise serializers.ValidationError('Select one valid answer and distinct options.')
        return d
class Quiz(serializers.Serializer):
    offering=serializers.IntegerField(min_value=1)
    title=serializers.CharField(max_length=150)
    deadline=serializers.DateTimeField()
    questions=Question(many=True,min_length=1,max_length=30)
class Attempt(serializers.Serializer):
    quiz=serializers.IntegerField(min_value=1)
    answers=serializers.ListField(child=serializers.IntegerField(min_value=0,max_value=5),min_length=1,max_length=30)

def roster(m):
    q=enrollments(m)
    return q.filter(student__status='Active') if m.role=='student' else q
def courses(m):
    q=offerings(m)
    return q.filter(enrollments__in=roster(m)).distinct() if m.role=='student' else q

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','faculty','student'])
    o=courses(m)
    es=roster(m)
    submissions=LearningSubmission.objects.filter(assignment__offering__in=o,enrollment__in=es)
    attempts=QuizAttempt.objects.filter(quiz__offering__in=o,enrollment__in=es)
    quizzes=list(LearningQuiz.objects.filter(offering__in=o).values('id','offering_id','title','deadline','questions'))
    # Answer keys are never included in the student response.
    if m.role=='student':
        for q in quizzes: q['questions']=[{'prompt':x['prompt'],'options':x['options']} for x in q['questions']]
    fields=['id','assignment_id','answer','marks','feedback','submitted_at']
    if m.role!='student': fields+=['enrollment__student__student_id','enrollment__student__name']
    data={'offerings':list(o.values('id','course__code','course__name','batch')),
          'resources':list(LearningResource.objects.filter(offering__in=o).order_by('-pk').values('id','offering_id','title','text','url')),
          'assignments':list(LearningAssignment.objects.filter(offering__in=o).order_by('-pk').values('id','offering_id','title','instructions','deadline','maximum')),
          'submissions':list(submissions.values(*fields)),
          'quizzes':quizzes,
          'attempts':list(attempts.values('quiz_id','score',*(['enrollment__student__student_id'] if m.role!='student' else [])))}
    response=Response(data); response['Cache-Control']='private, no-store'
    return response

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','faculty','student'])
    schemas={'resource':Resource,'assignment':Assignment,'submit':Submission,'grade':Grade,'quiz':Quiz,'attempt':Attempt}
    if action not in schemas: raise NotFound()
    if (action in ('submit','attempt'))!=(m.role=='student'): raise PermissionDenied()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            o=courses(m)
            es=roster(m)
            if action in ('resource','assignment','quiz'):
                offering=get(o,d.pop('offering'))
                if 'deadline' in d and d['deadline']<=timezone.now(): raise ValidationError('Deadline must be in the future.')
                model={'resource':LearningResource,'assignment':LearningAssignment,'quiz':LearningQuiz}[action]
                row=model.objects.create(offering=offering,**d)
            elif action=='submit':
                assignment=get(LearningAssignment.objects.filter(offering__in=o),d['assignment'])
                if assignment.deadline<timezone.now(): raise ValidationError('Submission deadline has passed.')
                enrollment=es.filter(offering=assignment.offering).first()
                if not enrollment: raise PermissionDenied()
                row=LearningSubmission.objects.create(assignment=assignment,enrollment=enrollment,answer=d['answer'])
            elif action=='grade':
                row=get(LearningSubmission.objects.filter(assignment__offering__in=o,enrollment__in=es),d['submission'])
                if row.marks is not None: raise ValidationError('Already graded; corrections require a separate review workflow.')
                if d['marks']>row.assignment.maximum: raise ValidationError('Marks exceed assignment maximum.')
                row.marks=d['marks'];row.feedback=d['feedback'];row.save(update_fields=['marks','feedback'])
            else:
                quiz=get(LearningQuiz.objects.filter(offering__in=o),d['quiz'])
                if quiz.deadline<timezone.now(): raise ValidationError('Quiz deadline has passed.')
                enrollment=es.filter(offering=quiz.offering).first()
                if not enrollment: raise PermissionDenied()
                answers=d['answers']
                if len(answers)!=len(quiz.questions) or any(a>=len(q['options']) for a,q in zip(answers,quiz.questions)): raise ValidationError('Answer each question with a valid option.')
                score=sum(a==q['correct'] for a,q in zip(answers,quiz.questions))
                row=QuizAttempt.objects.create(quiz=quiz,enrollment=enrollment,answers=answers,score=score)
            log(m,'learning.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid learning record.')
    return Response({'id':row.pk},status=201)
