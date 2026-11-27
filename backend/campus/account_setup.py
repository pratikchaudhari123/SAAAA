"""Institution-scoped account provisioning for the local evaluation release."""
import secrets
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Institution, Membership, Student, AuditEvent

ROLES=[('admissions','Admission officer'),('faculty','Faculty'),('finance','Finance officer'),('warden','Hostel warden'),('principal','Principal'),('student','Student'),('coe','Examination controller'),('viewer','Viewer'),('tpo','Placement officer'),('tpo_assistant','Placement assistant'),('company','Recruitment company')]

class AccountInput(serializers.Serializer):
    username=serializers.RegexField(regex=r'^[a-z0-9][a-z0-9_.-]{2,79}$',max_length=80)
    role=serializers.ChoiceField(choices=ROLES)
    student_id=serializers.CharField(max_length=50,required=False,allow_blank=True)
    def validate(self,data):
        if (data['role']=='student') != bool(data.get('student_id')):
            raise serializers.ValidationError('Student accounts must link one active student; non-student accounts must not include a student ID.')
        return data

@api_view(['GET','POST'])
def accounts(request,slug):
    m=Membership.objects.filter(institution__slug=slug,user=request.user,role='admin').first()
    if not m:
        raise PermissionDenied()
    if request.method=='GET':
        rows=list(Membership.objects.filter(institution=m.institution).order_by('user__username').values('id','role','user__username','user__is_active'))
        links=dict(Student.objects.filter(institution=m.institution,portal_user__isnull=False).values_list('portal_user__username','student_id'))
        for row in rows:
            row['student_id']=links.get(row['user__username'])
        available=list(Student.objects.filter(institution=m.institution,status='Active',portal_user__isnull=True).order_by('student_id').values('student_id','name'))
        return Response({'accounts':rows,'available_students':available,'roles':ROLES})
    form=AccountInput(data=request.data)
    form.is_valid(raise_exception=True)
    d=form.validated_data
    password=secrets.token_urlsafe(24)
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            student=None
            if d['role']=='student':
                student=Student.objects.select_for_update().filter(institution=m.institution,student_id=d['student_id'],status='Active',portal_user__isnull=True).first()
                if not student:
                    raise ValidationError('Student not available for account provisioning.')
            User=get_user_model()
            if User.objects.filter(username__iexact=d['username']).exists():
                raise ValidationError('Username unavailable. Choose another.')
            user=User.objects.create_user(username=d['username'],password=password)
            membership=Membership.objects.create(institution=m.institution,user=user,role=d['role'])
            if student:
                student.portal_user=user
                student.save(update_fields=['portal_user'])
            AuditEvent.objects.create(institution=m.institution,actor=m.user,action='account.provision',target=str(membership.pk))
    except IntegrityError:
        raise ValidationError('Account could not be created. Refresh and try a different username.')
    response=Response({'username':user.username,'password':password,'role':membership.role},status=201)
    response['Cache-Control']='no-store'
    return response
