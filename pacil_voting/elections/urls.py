from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    path('', views.election_list_view, name='list'),
    path('<int:pk>/', views.election_detail_view, name='detail'),
    path('create/', views.election_create_view, name='create'),
    path('<int:pk>/edit/', views.election_edit_view, name='edit'),
    path('<int:pk>/open/', views.election_open_view, name='open'),
    path('<int:pk>/close/', views.election_close_view, name='close'),
]
