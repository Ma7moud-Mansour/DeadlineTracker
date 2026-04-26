from django.contrib import admin
from .models import UniversityTask


@admin.register(UniversityTask)
class UniversityTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'user', 'due_date', 'is_completed', 'created_at')
    list_filter = ('is_completed', 'user', 'course')
    search_fields = ('title', 'course', 'user__username')
    list_editable = ('is_completed',)
    list_per_page = 25
    ordering = ('-created_at',)
