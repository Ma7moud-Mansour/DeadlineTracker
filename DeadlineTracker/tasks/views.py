from django.shortcuts import render, redirect
from django.contrib import messages
from .models import UniversityTask
from .scraper import run_msa_scraper

# 1. دالة الفورم وسحب البيانات (The Scraper View)
def sync_student_tasks(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        student_password = request.POST.get('student_password')
        
        # بنشغل السكريبت ببيانات الطالب
        success, result = run_msa_scraper(student_id, student_password)
        
        if success:
            for item in result:
                UniversityTask.objects.get_or_create(
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
def task_list_view(request):
    # هنجيب كل التاسكات من الداتابيز ونعكس الترتيب
    tasks = UniversityTask.objects.all().order_by('-created_at')
    return render(request, 'tasks/task_list.html', {'tasks': tasks})

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# الدالة دي بتستقبل الـ AJAX وتمسح التاسك أو تخليه True
def complete_task(request, task_id):
    if request.method == 'POST':
        try:
            task = UniversityTask.objects.get(id=task_id)
            task.is_completed = True
            task.save()
            return JsonResponse({'status': 'success'})
        except UniversityTask.DoesNotExist:
            return JsonResponse({'status': 'error'}, status=404)

# وعشان نعرض التاسكات اللي لسه مخلصتش بس في اللوحة، عدل دالة task_list_view كدة:
def task_list_view(request):
    # filter(is_completed=False) عشان ميجيبش اللي إنت دوست عليه Done
    tasks = UniversityTask.objects.filter(is_completed=False).order_by('-created_at')
    return render(request, 'tasks/task_list.html', {'tasks': tasks})