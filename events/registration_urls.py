from django.urls import path
from . import registration_views

urlpatterns = [
    path('', registration_views.my_registrations, name='my_registrations'),
    path('<int:pk>/', registration_views.registration_detail, name='registration_detail'),
]