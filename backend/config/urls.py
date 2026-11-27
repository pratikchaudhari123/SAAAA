from django.urls import path
from campus import views
urlpatterns = [path('api/health/',views.health),path('api/csrf/',views.csrf),path('api/login/',views.sign_in),path('api/logout/',views.sign_out),path('api/institutions/',views.institutions),path('api/institutions/<slug:slug>/students/',views.StudentList.as_view())]

from campus import workflows
urlpatterns += [path('api/institutions/<slug:slug>/students/<str:student_id>/admission/',workflows.admission_transition),path('api/institutions/<slug:slug>/audit/',workflows.audit_log)]
