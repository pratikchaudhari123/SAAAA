from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import transaction, IntegrityError, connection, DatabaseError
import json
from rest_framework import serializers, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Institution, Membership, Student, AuditEvent
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({'ok':True})
@require_POST
@csrf_protect
def sign_in(request):
    try:
        data = json.loads(request.body)
        user = authenticate(request,username=data['username'],password=data['password'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error':'Invalid request'},status=400)
    if user is None:
        return JsonResponse({'error':'Invalid credentials'},status=401)
    login(request,user)
    return JsonResponse({'username':user.get_username()})
@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({'ok':True})
@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({'service':'saaaa-api','status':'unhealthy','database':'unavailable'},status=503)
    return JsonResponse({'service':'saaaa-api','status':'healthy','database':'connected'})
@api_view(['GET'])
def institutions(request):
    return JsonResponse({'institutions':list(Membership.objects.filter(user=request.user).values('institution__slug','institution__name','role'))})
class StudentSerializer(serializers.ModelSerializer):
    year = serializers.IntegerField(min_value=1,max_value=8)
    class Meta:
        model = Student
        fields = ['student_id','name','email','program','year','status']
class StudentList(generics.ListCreateAPIView):
    serializer_class = StudentSerializer
    def membership(self):
        member = Membership.objects.filter(user=self.request.user,institution__slug=self.kwargs['slug']).first()
        if member is None or member.role in ('student','company','tpo','tpo_assistant'):
            raise PermissionDenied()
        return member
    def get_queryset(self):
        return Student.objects.filter(institution=self.membership().institution).order_by('student_id')
    def perform_create(self,serializer):
        member = self.membership()
        if member.role not in ('admin','admissions'):
            raise PermissionDenied()
        try:
            with transaction.atomic():
                student = serializer.save(institution=member.institution,status='Pending')
                AuditEvent.objects.create(institution=member.institution,actor=self.request.user,action='student.create',target=student.student_id)
        except IntegrityError:
            raise ValidationError({'student_id':'Student ID already exists in this institution.'})

@api_view(['GET'])
@permission_classes([AllowAny])
def session_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated':False})
    return JsonResponse({'authenticated':True,'username':request.user.get_username(),'institutions':list(Membership.objects.filter(user=request.user).values('institution__slug','institution__name','role'))})
