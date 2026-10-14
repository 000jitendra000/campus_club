from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    path('organizer/', views.organizer_dashboard, name='organizer_dashboard'),
    path('participant/', views.participant_dashboard, name='participant_dashboard'),
    path('hod/', views.hod_dashboard, name='hod_dashboard'),
]
