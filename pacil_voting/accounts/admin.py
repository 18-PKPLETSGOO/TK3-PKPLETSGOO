from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, LoginAttempt


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'role', 'nim', 'is_active')
    list_filter = ('role', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Role & NIM', {'fields': ('role', 'nim')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & NIM', {'fields': ('email', 'role', 'nim')}),
    )
    search_fields = ('email', 'username', 'nim')


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('email', 'ip_address', 'success', 'timestamp')
    list_filter = ('success',)
    readonly_fields = ('email', 'ip_address', 'success', 'timestamp')
    search_fields = ('email', 'ip_address')
