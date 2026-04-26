from django.db import models

class UniversityTask(models.Model):
    title = models.CharField(max_length=255) # اسم التاسك
    course = models.CharField(max_length=255) # اسم المادة
    due_date = models.CharField(max_length=255) # ميعاد التسليم (ممكن نخليه DateTimeField لاحقاً لو حابب تعمل فيه عمليات حسابية)
    created_at = models.DateTimeField(auto_now_add=True) # وقت السحب من الموقع
    is_completed = models.BooleanField(default=False) # هل خلصته ولا لأ

    def __str__(self):
        return f"{self.course} - {self.title}"