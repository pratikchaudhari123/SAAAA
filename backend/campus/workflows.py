"""Institution-scoped prototype business rules. Policy values are illustrative."""
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Membership, Student, AuditEvent

@api_view(['POST'])
def admission_transition(request, slug, student_id):
    member = Membership.objects.filter(user=request.user, institution__slug=slug, role__in=['admin','admissions']).first()
    if member is None:
        raise PermissionDenied()
    target = request.data.get('status')
    allowed = {'Pending': {'Active','On Hold'}, 'On Hold': {'Pending'}, 'Active': {'On Hold'}}
    with transaction.atomic():
        student = Student.objects.select_for_update().filter(institution=member.institution, student_id=student_id).first()
        if student is None:
            return Response({'detail':'Student not found'}, status=404)
        if not isinstance(target,str) or target not in allowed.get(student.status,set()):
            raise ValidationError({'status':'Invalid admission transition'})
        previous = student.status
        student.status = target
        student.save(update_fields=['status'])
        AuditEvent.objects.create(institution=member.institution,actor=request.user,action='admission.'+previous+'.'+target,target=student.student_id)
    return Response({'student_id':student.student_id,'status':student.status})

@api_view(['GET'])
def audit_log(request, slug):
    member = Membership.objects.filter(user=request.user,institution__slug=slug,role='admin').first()
    if member is None:
        raise PermissionDenied()
    return Response(list(AuditEvent.objects.filter(institution=member.institution).order_by('-created_at','-pk').values('actor__username','action','target','created_at')[:200]))
