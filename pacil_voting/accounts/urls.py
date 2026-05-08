from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('voters/', views.voter_list_view, name='voter_list'),
    path('voters/add/', views.add_voter_view, name='add_voter'),
    path('voters/<int:pk>/delete/', views.delete_voter_view, name='delete_voter'),
    path('candidates/', views.candidate_user_list_view, name='candidate_user_list'),
    path('candidates/add/', views.add_candidate_user_view, name='add_candidate_user'),
]
