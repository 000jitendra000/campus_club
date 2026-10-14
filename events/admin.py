from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'department', 'date', 'venue', 'status', 'created_at')
    list_filter = ('status', 'department')
    search_fields = ('title', 'organizer__username', 'department')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
