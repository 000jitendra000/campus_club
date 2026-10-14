from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Customised admin for the User model.
    Extends Django's built-in UserAdmin to add role and department fields.
    """

    # Columns shown in the user list view
    list_display = ('username', 'email', 'role', 'department', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'department')
    ordering = ('username',)

    # Fields shown on the user detail/edit page
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Campus Club', {
            'fields': ('role', 'department', 'roll_number'),
        }),
    )

    # Fields shown when creating a new user from admin
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Campus Club', {
            'classes': ('wide',),
            'fields': ('email', 'role', 'department'),
        }),
    )
