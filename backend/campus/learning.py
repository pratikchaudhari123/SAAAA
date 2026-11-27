"""Enrollment-scoped LMS pilot: text/link resources, text assignments, single-attempt MCQs."""
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, LearningResource, LearningAssignment, LearningSubmission, LearningQuiz, QuizAttempt
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
