from django.urls import path
from . import views

urlpatterns = [
    path('', views.ab_testing_index, name='ab_testing_index'),
    path('complete/<int:test_id>/', views.complete_ab_test, name='complete_ab_test'),
]
