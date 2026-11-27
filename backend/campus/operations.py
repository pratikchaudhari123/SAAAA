"""Local evaluation operations. Periods and courses are manually entered pending master data."""
from decimal import Decimal
from uuid import uuid4
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Membership, Student, AuditEvent, AttendanceEntry, FeeAccount, FeeReceipt, HostelBed, HostelCheck

def access(request,slug,role):
    m=Membership.objects.filter(user=request.user,institution__slug=slug).first()
    if not m or m.role not in ('admin',role):
        raise PermissionDenied('You do not have permission for this module.')
    return m

def student(m,identifier):
    s=Student.objects.select_for_update().filter(institution=m.institution,student_id=identifier,status='Active').first()
    if not s: raise ValidationError({'student_id':'Select an active student in this institution.'})
    return s

def audit(m,action,target):
    AuditEvent.objects.create(institution=m.institution,actor=m.user,action=action,target=str(target)[:100])

class Entry(serializers.Serializer):
    student_id=serializers.CharField(max_length=50)
    day=serializers.DateField()
    course=serializers.CharField(max_length=100)
    present=serializers.BooleanField()
    def validate_day(self,value):
        if value>timezone.localdate(): raise serializers.ValidationError('Future date not allowed.')
        return value

class Charge(serializers.Serializer):
    student_id=serializers.CharField(max_length=50)
    period=serializers.CharField(max_length=20)
    assessed=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=Decimal('0.01'))

class Receipt(serializers.Serializer):
    account=serializers.IntegerField(min_value=1)
    amount=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=Decimal('0.01'))
    method=serializers.ChoiceField(choices=['cash','bank'])

class Bed(serializers.Serializer):
    code=serializers.CharField(max_length=50)
    student_id=serializers.CharField(max_length=50,allow_blank=True,required=False)
    
class Check(serializers.Serializer):
    code=serializers.CharField(max_length=50)
    status=serializers.ChoiceField(choices=['present','absent','leave'])

def validated(cls,request):
    s=cls(data=request.data);s.is_valid(raise_exception=True);return s.validated_data

def fee_data(account):
    paid=account.receipts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return {'id':account.pk,'student_id':account.student.student_id,'name':account.student.name,'period':account.period,'assessed':str(account.assessed),'paid':str(paid),'balance':str(account.assessed-paid)}

@api_view(['GET','POST'])
def attendance(request,slug):
    m=access(request,slug,'faculty')
    if request.method=='POST':
        d=validated(Entry,request)
        with transaction.atomic():
            s=student(m,d.pop('student_id'))
            row,_=AttendanceEntry.objects.update_or_create(student=s,day=d['day'],course=d['course'],defaults={'present':d['present'],'recorded_by':m.user})
            audit(m,'attendance.save',row.pk)
        return Response({'id':row.pk},status=201)
    return Response(list(AttendanceEntry.objects.filter(student__institution=m.institution).order_by('-day','-pk').values('student__student_id','student__name','day','course','present','recorded_by__username')[:500]))

@api_view(['GET','POST'])
def fees(request,slug):
    m=access(request,slug,'finance')
    if request.method=='POST':
        d=validated(Charge,request)
        with transaction.atomic():
            s=student(m,d.pop('student_id'))
            account,created=FeeAccount.objects.get_or_create(student=s,period=d['period'],defaults={'assessed':d['assessed']})
            if not created: raise ValidationError('Fee already assessed for this period.')
            audit(m,'fee.assess',account.pk)
        return Response(fee_data(account),status=201)
    return Response([fee_data(a) for a in FeeAccount.objects.filter(student__institution=m.institution).select_related('student').order_by('-pk')[:500]])

@api_view(['GET','POST'])
def receipts(request,slug):
    m=access(request,slug,'finance')
    if request.method=='POST':
        d=validated(Receipt,request)
        with transaction.atomic():
            a=FeeAccount.objects.select_for_update().filter(pk=d['account'],student__institution=m.institution).first()
            if not a: raise NotFound()
            paid=a.receipts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            if d['amount']>a.assessed-paid: raise ValidationError('Amount exceeds outstanding balance.')
            r=FeeReceipt.objects.create(account=a,reference=uuid4(),amount=d['amount'],method=d['method'],recorded_by=m.user)
            audit(m,'fee.receipt',r.reference)
        return Response({'reference':str(r.reference),'amount':str(r.amount)},status=201)
    return Response(list(FeeReceipt.objects.filter(account__student__institution=m.institution).order_by('-pk').values('reference','account__student__student_id','amount','method','created_at','recorded_by__username')[:500]))

@api_view(['GET','POST'])
def beds(request,slug):
    m=access(request,slug,'warden')
    if request.method=='POST':
        d=validated(Bed,request)
        with transaction.atomic():
            Institution=type(m.institution)
            Institution.objects.select_for_update().get(pk=m.institution_id)
            b,_=HostelBed.objects.get_or_create(institution=m.institution,code=d['code'])
            if 'student_id' in d:
                if d['student_id']:
                    s=student(m,d['student_id'])
                    if not b.usable or (b.student_id and b.student_id!=s.pk): raise ValidationError('Bed unavailable.')
                    if HostelBed.objects.filter(student=s).exclude(pk=b.pk).exists(): raise ValidationError('Student already allocated.')
                    b.student=s
                else: b.student=None
                b.save(update_fields=['student'])
            audit(m,'hostel.bed',b.code)
        return Response({'code':b.code},status=201)
    return Response(list(HostelBed.objects.filter(institution=m.institution).order_by('code').values('code','usable','student__student_id','student__name')))

@api_view(['GET','POST'])
def hostel_checks(request,slug):
    m=access(request,slug,'warden')
    if request.method=='POST':
        d=validated(Check,request)
        with transaction.atomic():
            b=HostelBed.objects.select_for_update().filter(institution=m.institution,code=d['code']).first()
            if not b or not b.student_id: raise ValidationError('Allocate a student before verification.')
            row,_=HostelCheck.objects.update_or_create(student_id=b.student_id,day=timezone.localdate(),defaults={'bed':b,'status':d['status'],'recorded_by':m.user})
            audit(m,'hostel.check',row.pk)
        return Response({'id':row.pk},status=201)
    return Response(list(HostelCheck.objects.filter(student__institution=m.institution).order_by('-day','-pk').values('bed__code','student__student_id','day','status','recorded_by__username')[:500]))
