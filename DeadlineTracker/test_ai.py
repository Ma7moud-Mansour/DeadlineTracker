import sys
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DeadlineTracker.settings')
django.setup()

from tasks.views import process_ai_request
from django.test import RequestFactory
from django.contrib.auth.models import User
import json

rf = RequestFactory()
request = rf.post('/api/ai/', json.dumps({"mode":"plan"}), content_type='application/json')
user, _ = User.objects.get_or_create(username='test')
request.user = user
request.session = {}

try:
    response = process_ai_request(request)
    print('STATUS CODE:', response.status_code)
    print('CONTENT:', response.content.decode('utf-8'))
except Exception as e:
    print('EXCEPTION:', e)
