from rest_framework import serializers
from .models import UniversityTask

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = UniversityTask
        fields = '__all__'