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

from campus import hr
urlpatterns += [path('api/institutions/<slug:slug>/hr/',hr.workspace),path('api/institutions/<slug:slug>/hr/<str:action>/',hr.action)]

from campus import careers
urlpatterns += [path('api/institutions/<slug:slug>/careers/',careers.workspace),path('api/institutions/<slug:slug>/careers/<str:action>/',careers.action)]
urlpatterns += [path('api/institutions/<slug:slug>/careers/drives/<int:pk>/eligible/',careers.eligible)]

from campus import alumni
urlpatterns += [path('api/institutions/<slug:slug>/alumni/',alumni.workspace),path('api/institutions/<slug:slug>/alumni/<str:action>/',alumni.action)]

from campus import learning
urlpatterns += [path('api/institutions/<slug:slug>/learning/',learning.workspace),path('api/institutions/<slug:slug>/learning/<str:action>/',learning.action)]

from campus import ledger
urlpatterns += [path('api/institutions/<slug:slug>/ledger/',ledger.workspace),path('api/institutions/<slug:slug>/ledger/activate/',ledger.activate),path('api/institutions/<slug:slug>/ledger/manual/',ledger.manual)]

from campus import communications
urlpatterns += [path('api/institutions/<slug:slug>/communications/',communications.workspace),path('api/institutions/<slug:slug>/communications/<str:action>/',communications.action)]

from campus import registration
urlpatterns += [path('api/institutions/<slug:slug>/registration/',registration.workspace),path('api/institutions/<slug:slug>/registration/<str:action>/',registration.action),path('api/institutions/<slug:slug>/registration/documents/<int:pk>/',registration.document_view)]

from campus import permissions, documents
urlpatterns += [path('api/institutions/<slug:slug>/permissions/',permissions.workspace),path('api/institutions/<slug:slug>/permissions/<str:action>/',permissions.action),path('api/institutions/<slug:slug>/documents/',documents.workspace),path('api/institutions/<slug:slug>/documents/<str:action>/',documents.action)]

from campus import timetable
urlpatterns += [path('api/institutions/<slug:slug>/timetable/',timetable.workspace),path('api/institutions/<slug:slug>/timetable/<str:action>/',timetable.action)]

urlpatterns += [path('api/institutions/<slug:slug>/learning/attachments/<int:pk>/',learning.download)]
