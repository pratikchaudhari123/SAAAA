from django.urls import path
from campus import views
urlpatterns = [path('api/health/',views.health),path('api/csrf/',views.csrf),path('api/login/',views.sign_in),path('api/logout/',views.sign_out),path('api/institutions/',views.institutions),path('api/institutions/<slug:slug>/students/',views.StudentList.as_view())]

from campus import workflows
urlpatterns += [path('api/institutions/<slug:slug>/students/<str:student_id>/admission/',workflows.admission_transition),path('api/institutions/<slug:slug>/audit/',workflows.audit_log)]

urlpatterns += [path('api/session/',views.session_status)]

from campus import operations
urlpatterns += [path('api/institutions/<slug:slug>/operations/'+name+'/',getattr(operations,name)) for name in ['attendance','fees','receipts','beds','hostel_checks']]

from campus import platform
urlpatterns += [path('api/institutions/<slug:slug>/setup/<str:kind>/',platform.master),path('api/institutions/<slug:slug>/setup/<str:kind>/<int:pk>/status/',platform.master_status),path('api/institutions/<slug:slug>/dashboard/',platform.dashboard)]

from campus import student_portal
urlpatterns += [path('api/institutions/<slug:slug>/my-campus/',student_portal.my_campus)]
