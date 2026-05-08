from django.contrib import admin
from .models import Vote


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('election', 'timestamp', 'anonymous_token')
    list_filter = ('election',)
    readonly_fields = ('voter', 'election', 'candidate', 'timestamp', 'anonymous_token')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
