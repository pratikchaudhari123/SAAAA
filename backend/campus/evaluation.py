"""Question-wise assessment pilot. Scanned pages are managed by the separate private scan endpoint."""
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Membership, ExamQuestion, BookEvaluation, QuestionScore, ExamApplication
from .academic_engine import member, exams, applications, get, parse, log

class QuestionInput(serializers.Serializer):
    exam=serializers.IntegerField(min_value=1)
    code=serializers.CharField(max_length=20)
    maximum=serializers.IntegerField(min_value=1,max_value=1000)
    course_outcome=serializers.CharField(max_length=40,allow_blank=True,required=False,default='')
    bloom_level=serializers.IntegerField(min_value=1,max_value=6,allow_null=True,required=False,default=None)
class AssignInput(serializers.Serializer):
    application=serializers.IntegerField(min_value=1)
    examiner=serializers.IntegerField(min_value=1)
    expected_pages=serializers.IntegerField(min_value=1,max_value=40,required=False,allow_null=True,default=None)
class ScoreInput(serializers.Serializer):
    evaluation=serializers.IntegerField(min_value=1)
    question=serializers.IntegerField(min_value=1)
    marks=serializers.IntegerField(min_value=0,max_value=1000)
    note=serializers.CharField(max_length=300,allow_blank=True,required=False,default='')
class SubmitInput(serializers.Serializer):
    evaluation=serializers.IntegerField(min_value=1)
class ReviewInput(SubmitInput):
    decision=serializers.ChoiceField(choices=['approved','returned'])
    note=serializers.CharField(max_length=300,allow_blank=True,required=False,default='')

def scoped(m):
    q=BookEvaluation.objects.filter(application__exam__offering__course__program__department__institution=m.institution,application__enrollment__student__institution=m.institution,examiner__institution=m.institution)
    return q.filter(examiner=m) if m.role=='faculty' else q

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','coe','faculty'])
    fields=['id','book_ref','expected_pages','application__exam_id','application__exam__title','status','review_note','assigned_at','submitted_at','reviewed_at','examiner__user__username']
    if m.role!='faculty': fields+=['application_id','application__enrollment__student__student_id']
    books=list(scoped(m).order_by('-pk').values(*fields))
    exam_ids={b['application__exam_id'] for b in books}
    if m.role!='faculty':
        exam_ids=set(exams(m).values_list('pk',flat=True))
    result={'books':books,'questions':list(ExamQuestion.objects.filter(exam_id__in=exam_ids).order_by('exam_id','pk').values('id','exam_id','code','maximum','course_outcome','bloom_level')),'scores':list(QuestionScore.objects.filter(evaluation__in=scoped(m)).values('evaluation_id','question_id','marks','note'))}
    if m.role!='faculty':
        result['exams']=list(exams(m).order_by('-day').values('id','title','maximum','status'))
        result['applications']=list(applications(m).filter(exam__status='closed',exam__questions__isnull=False,marks__isnull=True,evaluation__isnull=True).distinct().values('id','exam_id','exam__title','enrollment__student__student_id'))
        result['examiners']=list(Membership.objects.filter(institution=m.institution,role='faculty',user__is_active=True).values('id','user__username'))
    return Response(result)

@api_view(['POST'])
def action(request,slug,action):
    m=member(request,slug,['admin','coe','faculty'])
    staff=m.role in ('admin','coe')
    if (action in ('question','assign','review') and not staff) or (action in ('score','submit') and m.role!='faculty'):
        raise PermissionDenied()
    schemas={'question':QuestionInput,'assign':AssignInput,'score':ScoreInput,'submit':SubmitInput,'review':ReviewInput}
    if action not in schemas: raise NotFound()
    d=parse(schemas[action],request)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            if action=='question':
                exam=get(exams(m),d.pop('exam'))
                if exam.status!='open': raise ValidationError('Question plan is locked when applications close.')
                total=exam.questions.aggregate(total=Sum('maximum'))['total'] or 0
                if total+d['maximum']>exam.maximum: raise ValidationError('Question maximums exceed examination maximum.')
                row=ExamQuestion.objects.create(exam=exam,**d)
            elif action=='assign':
                app=get(applications(m),d['application'])
                exam=app.exam
                if exam.status!='closed' or exam.day>timezone.localdate() or app.marks is not None: raise ValidationError('Only unmarked, closed examinations on or after their date can be assigned.')
                if (exam.questions.aggregate(total=Sum('maximum'))['total'] or 0)!=exam.maximum: raise ValidationError('Complete the question plan before assigning.')
                f=get(Membership.objects.filter(institution=m.institution,role='faculty',user__is_active=True),d['examiner'])
                row=BookEvaluation.objects.create(application=app,examiner=f,expected_pages=d['expected_pages'])
            else:
                evaluation=get(scoped(m),d['evaluation'])
                exam=evaluation.application.exam
                if exam.status!='closed' or exam.day>timezone.localdate(): raise ValidationError('Evaluation is locked or exam date not reached.')
                if action=='score':
                    if evaluation.status not in ('assigned','returned'): raise ValidationError('Submitted evaluation is locked.')
                    q=get(exam.questions.all(),d['question'])
                    if d['marks']>q.maximum: raise ValidationError('Marks exceed question maximum.')
                    row,_=QuestionScore.objects.update_or_create(evaluation=evaluation,question=q,defaults={'marks':d['marks'],'note':d['note']})
                elif action=='submit':
                    if evaluation.status not in ('assigned','returned'): raise ValidationError('Evaluation cannot be submitted again.')
                    if evaluation.expected_pages is not None and set(evaluation.pages.values_list('number',flat=True))!=set(range(1,evaluation.expected_pages+1)): raise ValidationError('All declared answer pages must be uploaded before submission.')
                    required=set(exam.questions.values_list('pk',flat=True))
                    actual=set(evaluation.scores.values_list('question_id',flat=True))
                    if not required or required!=actual: raise ValidationError('Score every question before submission.')
                    evaluation.status='submitted'
                    evaluation.submitted_at=timezone.now()
                    evaluation.save(update_fields=['status','submitted_at'])
                    row=evaluation
                else:
                    if evaluation.status!='submitted': raise ValidationError('Review requires a submitted evaluation.')
                    if d['decision']=='returned' and not d['note'].strip(): raise ValidationError('Provide a reason for returning.')
                    if d['decision']=='approved':
                        required=dict(exam.questions.values_list('pk','maximum'))
                        scores=dict(evaluation.scores.values_list('question_id','marks'))
                        if not required or required.keys()!=scores.keys() or sum(required.values())!=exam.maximum or any(scores[k]>v for k,v in required.items()): raise ValidationError('Question scores are incomplete or invalid.')
                        evaluation.application.marks=sum(scores.values())
                        evaluation.application.save(update_fields=['marks'])
                    evaluation.status=d['decision']
                    evaluation.review_note=d['note']
                    evaluation.reviewed_at=timezone.now()
                    evaluation.reviewed_by=m.user
                    evaluation.save(update_fields=['status','review_note','reviewed_at','reviewed_by'])
                    row=evaluation
            log(m,'evaluation.'+action,row)
    except IntegrityError:
        raise ValidationError('Duplicate or invalid evaluation record.')
    return Response({'id':row.pk},status=201)
