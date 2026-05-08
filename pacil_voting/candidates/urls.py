from django.urls import path
from . import views

app_name = 'candidates'

urlpatterns = [
    path('my-profile/', views.candidate_edit_profile_view, name='my_profile'),
    path('election/<int:election_pk>/add/', views.candidate_create_view, name='create'),
    path('<int:pk>/edit/', views.candidate_edit_view, name='edit'),
    path('<int:pk>/delete/', views.candidate_delete_view, name='delete'),
]
