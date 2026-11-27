from decimal import Decimal
from django.db import transaction, IntegrityError
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Institution, Membership, Department, AcademicProgram, AcademicCourse, AcademicPeriod, Student, AttendanceEntry, FeeAccount, FeeReceipt, HostelBed, HostelCheck, AuditEvent

class DepartmentInput(serializers.Serializer):
    code=serializers.SlugField(max_length=30)
    name=serializers.CharField(max_length=150)

class ProgramInput(DepartmentInput):
    department=serializers.IntegerField(min_value=1)
    duration_years=serializers.IntegerField(min_value=1,max_value=8)
    intake=serializers.IntegerField(min_value=1,max_value=10000)

class CourseInput(DepartmentInput):
    program=serializers.IntegerField(min_value=1)
    semester=serializers.IntegerField(min_value=1,max_value=16)
    credits=serializers.IntegerField(min_value=0,max_value=30)

class PeriodInput(serializers.Serializer):
    code=serializers.SlugField(max_length=20)
    starts=serializers.DateField()
    ends=serializers.DateField()
    def validate(self,data):
        if data['ends']<data['starts']: raise serializers.ValidationError('End date must follow start date.')
        return data

def admin(request,slug):
    m=Membership.objects.filter(user=request.user,institution__slug=slug,role='admin').first()
    if not m: raise PermissionDenied()
    return m

def registry(m):
    return {
        'departments':(Department.objects.filter(institution=m.institution),DepartmentInput,['id','code','name','active']),
        'programs':(AcademicProgram.objects.filter(department__institution=m.institution),ProgramInput,['id','code','name','department_id','duration_years','intake','active']),
        'courses':(AcademicCourse.objects.filter(program__department__institution=m.institution),CourseInput,['id','code','name','program_id','semester','credits','active']),
        'periods':(AcademicPeriod.objects.filter(institution=m.institution),PeriodInput,['id','code','starts','ends','active']),
    }

@api_view(['GET','POST'])
def master(request,slug,kind):
    m=admin(request,slug)
    reg=registry(m)
    if kind not in reg: raise ValidationError('Unknown master type.')
    qs,cls,fields=reg[kind]
    if request.method=='GET': return Response(list(qs.order_by('code','pk').values(*fields)))
    serializer=cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    d=serializer.validated_data
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            if kind in ('departments','periods'): d['institution']=m.institution
            if kind=='programs':
                parent=reg['departments'][0].filter(pk=d.pop('department'),active=True).first()
                if not parent: raise ValidationError('Choose an active department in this institution.')
                d['department']=parent
            if kind=='courses':
                parent=reg['programs'][0].filter(pk=d.pop('program'),active=True,department__active=True).first()
                if not parent: raise ValidationError('Choose an active program in this institution.')
                if d['semester']>parent.duration_years*2: raise ValidationError('Semester exceeds program duration.')
                d['program']=parent
            row=qs.model.objects.create(**d)
            AuditEvent.objects.create(institution=m.institution,actor=m.user,action='master.create.'+kind,target=str(row.pk))
    except IntegrityError:
        raise ValidationError('A record with this code already exists in the selected scope.')
    return Response(qs.filter(pk=row.pk).values(*fields).get(),status=201)

@api_view(['POST'])
def master_status(request,slug,kind,pk):
    m=admin(request,slug)
    reg=registry(m)
    if kind not in reg: raise ValidationError('Unknown master type.')
    active=request.data.get('active')
    if not isinstance(active,bool): raise ValidationError('active must be a boolean.')
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        row=reg[kind][0].filter(pk=pk).first()
        if not row: raise ValidationError('Record not available in this institution.')
        if not active and kind=='departments' and AcademicProgram.objects.filter(department=row,active=True).exists(): raise ValidationError('Deactivate dependent programs first.')
        if not active and kind=='programs' and AcademicCourse.objects.filter(program=row,active=True).exists(): raise ValidationError('Deactivate dependent courses first.')
        if active and kind=='programs' and not row.department.active: raise ValidationError('Department is inactive.')
        if active and kind=='courses' and (not row.program.active or not row.program.department.active): raise ValidationError('Parent program or department is inactive.')
        row.active=active
        row.save(update_fields=['active'])
        AuditEvent.objects.create(institution=m.institution,actor=m.user,action='master.status.'+kind,target=str(row.pk))
    return Response({'id':row.pk,'active':active})

@api_view(['GET'])
def dashboard(request,slug):
    m=Membership.objects.filter(user=request.user,institution__slug=slug,role__in=['admin','principal']).first()
    if not m: raise PermissionDenied()
    i=m.institution
    students=Student.objects.filter(institution=i)
    attendance=AttendanceEntry.objects.filter(student__institution=i,day=timezone.localdate())
    beds=HostelBed.objects.filter(institution=i)
    fees=FeeAccount.objects.filter(student__institution=i)
    assessed=fees.aggregate(total=Sum('assessed'))['total'] or Decimal('0.00')
    paid=FeeReceipt.objects.filter(account__student__institution=i).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return Response({'date':str(timezone.localdate()),'students':students.count(),'active_students':students.filter(status='Active').count(),'pending_admissions':students.filter(status='Pending').count(),'attendance_entries_today':attendance.count(),'present_entries_today':attendance.filter(present=True).count(),'fee_assessed':str(assessed),'fee_received':str(paid),'fee_outstanding':str(assessed-paid),'beds':beds.count(),'allocated_beds':beds.filter(student__isnull=False).count(),'usable_vacant_beds':beds.filter(student__isnull=True,usable=True).count(),'hostel_checks_today':HostelCheck.objects.filter(student__institution=i,day=timezone.localdate()).count(),'departments':Department.objects.filter(institution=i,active=True).count(),'programs':AcademicProgram.objects.filter(department__institution=i,active=True).count(),'courses':AcademicCourse.objects.filter(program__department__institution=i,active=True).count(),'program_breakdown':list(students.values('program').annotate(total=Count('id')).order_by('program')),'recent_activity':[] if m.role=='principal' else list(AuditEvent.objects.filter(institution=i).order_by('-created_at').values('action','target','actor__username','created_at')[:15])})
