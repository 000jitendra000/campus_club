from django.urls import path
from . import views
from . import registration_views

urlpatterns = [
    # Organizer: events
    path('', views.event_list, name='event_list'),
    path('create/', views.event_create, name='event_create'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    path('<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('<int:pk>/submit/', views.event_submit, name='event_submit'),

    # Organizer: registration form builder
    path('<int:pk>/form-builder/', registration_views.form_builder, name='form_builder'),
    path('<int:pk>/form-builder/<int:field_pk>/edit/',
         registration_views.form_field_edit, name='form_field_edit'),
    path('<int:pk>/form-builder/<int:field_pk>/delete/',
         registration_views.form_field_delete, name='form_field_delete'),

    # Organizer: applicants
    path('<int:pk>/applicants/', registration_views.applicant_list, name='applicant_list'),
    path('<int:pk>/applicants/<int:registration_pk>/',
         registration_views.applicant_detail, name='applicant_detail'),

    # Organizer: attendance
    path('<int:pk>/attendance/', registration_views.attendance, name='attendance'),
    path('<int:pk>/attendance/<int:registration_pk>/mark/',
         registration_views.attendance_mark, name='attendance_mark'),

    # HOD review
    path('review/', views.hod_event_list, name='hod_event_list'),
    path('review/<int:pk>/', views.hod_event_detail, name='hod_event_detail'),
    path('review/<int:pk>/approve/', views.hod_event_approve, name='hod_event_approve'),
    path('review/<int:pk>/reject/', views.hod_event_reject, name='hod_event_reject'),

    # Student browsing + applying
    path('browse/', views.student_event_list, name='student_event_list'),
    path('browse/<int:pk>/', views.student_event_detail, name='student_event_detail'),
    path('browse/<int:pk>/register/', registration_views.event_register, name='event_register'),
]