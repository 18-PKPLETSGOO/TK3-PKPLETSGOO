from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('logs/', views.audit_log_view, name='logs'),
    path('results/<int:election_pk>/', views.results_view, name='results'),
]
