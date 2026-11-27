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

from campus import connect
urlpatterns += [path('api/connect/events/',connect.ingest),path('api/institutions/<slug:slug>/connect/sources/',connect.sources),path('api/institutions/<slug:slug>/connect/sources/<int:pk>/action/',connect.source_action),path('api/institutions/<slug:slug>/connect/events/',connect.events),path('api/institutions/<slug:slug>/connect/student-import/',connect.student_import),path('api/institutions/<slug:slug>/connect/import-history/',connect.import_history)]

from campus import academic_engine
urlpatterns += [path('api/institutions/<slug:slug>/academic-engine/',academic_engine.academics),path('api/institutions/<slug:slug>/academic-engine/<str:action>/',academic_engine.academic_action),path('api/institutions/<slug:slug>/examination/',academic_engine.examination),path('api/institutions/<slug:slug>/examination/<str:action>/',academic_engine.exam_action)]

from campus import account_setup
urlpatterns += [path('api/institutions/<slug:slug>/accounts/',account_setup.accounts)]

from campus import evaluation
urlpatterns += [path('api/institutions/<slug:slug>/evaluation/',evaluation.workspace),path('api/institutions/<slug:slug>/evaluation/<str:action>/',evaluation.action)]

from campus import scans
urlpatterns += [path('api/institutions/<slug:slug>/evaluation/books/<int:pk>/pages/',scans.pages),path('api/institutions/<slug:slug>/evaluation/books/<int:pk>/pages/<int:page_id>/image/',scans.image_view),path('api/institutions/<slug:slug>/evaluation/books/<int:pk>/pages/<int:page_id>/annotations/',scans.annotations)]
