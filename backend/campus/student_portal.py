"""Student self-service: identity derived exclusively from authenticated membership."""
from django.db.models import Sum
from decimal import Decimal
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .models import Membership, Student, AttendanceEntry, FeeAccount, HostelBed
from .views import StudentSerializer

@api_view(['GET'])
def my_campus(request,slug):
    membership=Membership.objects.filter(user=request.user,institution__slug=slug,role='student').first()
    if not membership:
        raise PermissionDenied()
    student=Student.objects.filter(institution=membership.institution,portal_user=request.user).first()
    if not student:
        raise PermissionDenied('No student record linked to your account. Contact the admissions office.')
    attendance=AttendanceEntry.objects.filter(student=student)
    total=attendance.count()
    present=attendance.filter(present=True).count()
    fees=[]
    for a in FeeAccount.objects.filter(student=student).annotate(received=Sum('receipts__amount')).order_by('-period'):
        paid=a.received or Decimal('0.00')
        fees.append({'period':a.period,'assessed':str(a.assessed),'paid':str(paid),'balance':str(a.assessed-paid)})
    bed=HostelBed.objects.filter(institution=membership.institution,student=student).values('code').first()
    return Response({'profile':StudentSerializer(student).data,'attendance':{'total':total,'present':present,'percent':round(present*100/total,1) if total else None,'recent':list(attendance.order_by('-day','-pk').values('day','course','present')[:50])},'fees':fees,'hostel':bed})
