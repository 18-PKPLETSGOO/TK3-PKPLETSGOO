from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'actor_email', 'ip_address')
    list_filter = ('action',)
    readonly_fields = (
        'action', 'actor', 'actor_email', 'ip_address',
        'timestamp', 'details', 'log_hash'
    )
    search_fields = ('actor_email', 'action')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
