from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Root redirect to login
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False), name='home'),

    # Django admin
    path('admin/', admin.site.urls),

    # Accounts (login, logout, register)
    path('accounts/', include('accounts.urls')),

    # Dashboard routes
    path('dashboard/', include('accounts.dashboard_urls')),

    # Events (organizer CRUD)
    path('events/', include('events.urls')),

    # Student registrations (My Registrations)
    path('registrations/', include('events.registration_urls')),
]
