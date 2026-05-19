# tasks/urls.py

from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    # Auth
    path('', views.sync_student_tasks, name='sync-form'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

    # Dashboard
    path('dashboard/', views.task_list_view, name='task-list'),
    path('complete-task/<int:task_id>/', views.complete_task, name='complete-task'),

    # Data export
    path('export/json/', views.export_json_view, name='export-json'),
    path('export/xml/',  views.export_xml_view,  name='export-xml'),

    # EDA
    path('eda/', views.eda_view, name='eda'),

    # AI Assistant  (modes: roaster, plan, break, classify, summarize, sentiment)
    path('api/ai/', views.process_ai_request, name='process-ai'),

    # Phase 2 — Feature Extraction
    path('api/features/', views.features_view, name='features'),

    # Phase 2 — Evaluation
    path('api/evaluation/', views.evaluation_view, name='evaluation'),

    # Phase 2 — IR Search
    path('api/search/', views.search_view, name='search'),
]
