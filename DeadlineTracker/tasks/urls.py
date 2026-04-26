# tasks/urls.py

from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.sync_student_tasks, name='sync-form'),      # اللينك: / (الفورم)
    path('dashboard/', views.task_list_view, name='task-list'), # اللينك: /dashboard/
    path('complete-task/<int:task_id>/', views.complete_task, name='complete-task'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
]