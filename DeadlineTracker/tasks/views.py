from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UniversityTask
from .scraper import run_msa_scraper


# 1. دالة الفورم وسحب البيانات (The Sync / Login View)
def sync_student_tasks(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        student_password = request.POST.get('student_password')

        # بنشغل السكريبت ببيانات الطالب
        success, result = run_msa_scraper(student_id, student_password)

        if success:
            # Auto-register: لو اليوزر مش موجود بننشئه
            user, created = User.objects.get_or_create(
                username=student_id,
                defaults={'first_name': student_id}
            )

            # بنسجل دخول اليوزر
            login(request, user)

            # بنحفظ التاسكات مربوطة باليوزر الحالي
            for item in result:
                UniversityTask.objects.get_or_create(
                    user=request.user,
                    title=item['title'],
                    course=item['course'],
                    due_date=item['due_date']
                )

            messages.success(request, 'تم سحب التاسكات بنجاح يا هندسة!')
            return redirect('task-list')
        else:
            messages.error(request, f'حصلت مشكلة: {result}')

    return render(request, 'tasks/sync_form.html')


# 2. دالة عرض التاسكات في اللوحة (The Dashboard View)
@login_required
def task_list_view(request):
    # filter by user عشان كل واحد يشوف تاسكاته بس
    tasks = UniversityTask.objects.filter(
        user=request.user, is_completed=False
    ).order_by('-created_at')
    return render(request, 'tasks/task_list.html', {'tasks': tasks})


# 3. الدالة دي بتستقبل الـ AJAX وتمسح التاسك أو تخليه True
@login_required
def complete_task(request, task_id):
    if request.method == 'POST':
        try:
            task = UniversityTask.objects.get(id=task_id, user=request.user)
            task.is_completed = True
            task.save()
            return JsonResponse({'status': 'success'})
        except UniversityTask.DoesNotExist:
            return JsonResponse({'status': 'error'}, status=404)