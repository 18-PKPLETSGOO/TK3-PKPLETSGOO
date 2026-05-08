from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    path('election/<int:election_pk>/cast/', views.cast_vote_view, name='cast'),
    path('election/<int:election_pk>/status/', views.vote_status_view, name='status'),
]
