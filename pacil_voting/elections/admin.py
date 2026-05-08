from django.contrib import admin
from .models import Election


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'start_date', 'end_date', 'created_by')
    list_filter = ('status',)
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('title',)
