"""Authorized integration boundary. No raw biometric data or remote DB credentials."""
import csv
import hashlib
import io
import secrets
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from .models import Institution, Membership, Student, AuditEvent, IntegrationSource, IntegrationEvent, StudentImportBatch
from .views import StudentSerializer

def admin(request,slug):
    member=Membership.objects.filter(user=request.user,institution__slug=slug,role='admin').first()
    if not member:
        raise PermissionDenied()
    return member

def audit(member,action,target):
    AuditEvent.objects.create(institution=member.institution,actor=member.user,action=action,target=str(target))

def digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

class SourceInput(serializers.Serializer):
    name=serializers.CharField(max_length=100)
    purpose=serializers.ChoiceField(choices=['classroom','employee','exam','hostel'])

class EventInput(serializers.Serializer):
    external_id=serializers.CharField(max_length=100)
    subject_ref=serializers.RegexField(regex=r'^[A-Za-z0-9_.:-]+$',max_length=100)
    event_type=serializers.ChoiceField(choices=['attendance','in','out'])
    occurred_at=serializers.CharField(max_length=40)
    def validate_occurred_at(self,value):
        try:
            dt=parse_datetime(value)
        except ValueError:
            dt=None
        if dt is None or timezone.is_naive(dt):
            raise serializers.ValidationError('Use ISO-8601 with explicit time zone.')
        if dt>timezone.now()+timedelta(minutes=5):
            raise serializers.ValidationError('Event is in the future.')
        return dt

def validate(cls,data):
    if not isinstance(data,dict):
        raise ValidationError('JSON object required.')
    form=cls(data=data)
    if set(data)-set(form.fields):
        raise ValidationError('Unknown fields are not accepted.')
    form.is_valid(raise_exception=True)
    return form.validated_data

@api_view(['GET','POST'])
def sources(request,slug):
    m=admin(request,slug)
    if request.method=='GET':
        return Response(list(IntegrationSource.objects.filter(institution=m.institution).order_by('name').values('id','name','purpose','active','last_received_at')))
    d=validate(SourceInput,request.data)
    token=secrets.token_urlsafe(32)
    try:
        with transaction.atomic():
            row=IntegrationSource.objects.create(institution=m.institution,token_digest=digest(token),**d)
            audit(m,'integration.source.create',row.pk)
    except IntegrityError:
        raise ValidationError('Source name already exists.')
    response=Response({'id':row.pk,'token':token},status=201)
    response['Cache-Control']='no-store'
    return response

@api_view(['POST'])
def source_action(request,slug,pk):
    m=admin(request,slug)
    action=request.data.get('action')
    if action not in ('disable','rotate'):
        raise ValidationError('Choose disable or rotate.')
    with transaction.atomic():
        row=IntegrationSource.objects.select_for_update().filter(institution=m.institution,pk=pk).first()
        if not row:
            raise NotFound()
        result={'id':row.pk}
        if action=='disable':
            row.active=False
        else:
            token=secrets.token_urlsafe(32)
            row.token_digest=digest(token)
            row.active=True
            result['token']=token
        row.save(update_fields=['active','token_digest'])
        audit(m,'integration.source.'+action,row.pk)
    response=Response(result)
    response['Cache-Control']='no-store'
    return response

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def ingest(request):
    # Machine-only bearer authentication; browser sessions are deliberately ignored.
    header=request.headers.get('Authorization','')
    if not header.startswith('Bearer ') or len(header)>160:
        return Response({'detail':'Valid integration token required.'},status=401)
    if not request.content_type.startswith('application/json'):
        return Response({'detail':'JSON required.'},status=415)
    if len(request.body)>16384:
        return Response({'detail':'Event too large.'},status=413)
    token=header[7:]
    with transaction.atomic():
        source=IntegrationSource.objects.select_for_update().filter(token_digest=digest(token),active=True).first()
        if not source:
            return Response({'detail':'Valid integration token required.'},status=401)
        d=validate(EventInput,request.data)
        event,created=IntegrationEvent.objects.get_or_create(source=source,external_id=d['external_id'],defaults={k:v for k,v in d.items() if k!='external_id'})
        if not created and any(getattr(event,k)!=v for k,v in d.items()):
            return Response({'detail':'Event identifier conflicts with existing record.'},status=409)
        from .hr import project_employee_event
        posted=project_employee_event(event) if created else hasattr(event,'employee_punch')
        source.last_received_at=timezone.now()
        source.save(update_fields=['last_received_at'])
    return Response({'id':event.pk,'status':'employee_punch' if posted else 'staged','duplicate':not created},status=201 if created else 200)

@api_view(['GET'])
def events(request,slug):
    m=admin(request,slug)
    qs=IntegrationEvent.objects.filter(source__institution=m.institution).order_by('-received_at','-pk')
    return Response({'total':qs.count(),'events':list(qs[:100].values('external_id','source__name','source__purpose','subject_ref','event_type','occurred_at','received_at'))})

HEADERS=['student_id','name','email','program','year']
def parse_students(raw,institution):
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>512000:
        raise ValidationError('CSV must be text and at most 500 KB.')
    try:
        reader=csv.DictReader(io.StringIO(raw.lstrip('\ufeff')),strict=True)
        if reader.fieldnames!=HEADERS:
            raise ValidationError('CSV columns must be: '+','.join(HEADERS))
        records=[]
        seen=set()
        errors=[]
        for line,row in enumerate(reader,2):
            if line>501:
                raise ValidationError('Maximum 500 rows per batch.')
            if None in row or any(v is None for v in row.values()):
                errors.append({'row':line,'error':'Incorrect number of columns.'})
                continue
            form=StudentSerializer(data={**row,'status':'Pending'})
            if not form.is_valid():
                errors.append({'row':line,'error':'Invalid fields: '+', '.join(form.errors.keys())})
                continue
            d=form.validated_data
            if d['student_id'] in seen:
                errors.append({'row':line,'error':'Duplicate student ID in file.'})
                continue
            seen.add(d['student_id'])
            records.append(d)
    except csv.Error:
        raise ValidationError('Invalid CSV format.')
    if not records and not errors:
        raise ValidationError('CSV has no student rows.')
    existing=set(Student.objects.filter(institution=institution,student_id__in=seen).values_list('student_id',flat=True))
    pending=[r for r in records if r['student_id'] not in existing]
    return pending,{'valid_rows':len(records),'new_rows':len(pending),'existing_rows':len(existing),'errors':errors}

@api_view(['POST'])
def student_import(request,slug):
    m=admin(request,slug)
    mode=request.data.get('mode')
    raw=request.data.get('csv')
    if mode not in ('preview','apply'):
        raise ValidationError('Select preview or apply.')
    if mode=='preview':
        _,report=parse_students(raw,m.institution)
        report['file_digest']=digest(raw)
        return Response(report)
    if not isinstance(raw,str) or request.data.get('file_digest')!=digest(raw):
        raise ValidationError('Preview this exact file before applying.')
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            rows,report=parse_students(raw,m.institution)
            if report['errors']:
                raise ValidationError({'detail':'Correct CSV validation errors before importing.'})
            Student.objects.bulk_create([Student(institution=m.institution,**r) for r in rows])
            batch=StudentImportBatch.objects.create(institution=m.institution,actor=m.user,row_count=report['valid_rows'],created_count=len(rows),skipped_count=report['existing_rows'])
            audit(m,'integration.student_import',batch.pk)
    except IntegrityError:
        raise ValidationError('Records changed during import. Preview again; no rows were committed.')
    return Response({**report,'batch_id':batch.pk,'status':'Imported new records as Pending; existing records unchanged.'},status=201)

@api_view(['GET'])
def import_history(request,slug):
    m=admin(request,slug)
    return Response(list(StudentImportBatch.objects.filter(institution=m.institution).order_by('-pk')[:50].values('id','row_count','created_count','skipped_count','created_at','actor__username')))
