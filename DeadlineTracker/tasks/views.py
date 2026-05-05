import os

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings

from .models import UniversityTask
from .scraper import run_msa_scraper


# ─────────────────────────────────────────────────────────────────────────────
# 1. Sync / Login View
# ─────────────────────────────────────────────────────────────────────────────

def sync_student_tasks(request):
    if request.method == 'POST':
        student_id       = request.POST.get('student_id')
        student_password = request.POST.get('student_password')

        success, result = run_msa_scraper(student_id, student_password)

        if success:
            user, _ = User.objects.get_or_create(
                username=student_id,
                defaults={'first_name': student_id}
            )
            login(request, user)

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


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dashboard View
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def task_list_view(request):
    tasks = UniversityTask.objects.filter(
        user=request.user, is_completed=False
    ).order_by('-created_at')
    return render(request, 'tasks/task_list.html', {'tasks': tasks})


# ─────────────────────────────────────────────────────────────────────────────
# 3. Complete Task (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# 4. Data Export Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def export_json_view(request):
    """Export the current user's tasks as a JSON file download."""
    from .export import export_to_json

    filepath = os.path.join(
        getattr(settings, 'MEDIA_ROOT', 'media'),
        'exports',
        f'tasks_{request.user.username}.json',
    )
    export_to_json(filepath=filepath, user=request.user)

    if not os.path.exists(filepath):
        raise Http404("Export file not found.")

    return FileResponse(
        open(filepath, 'rb'),
        as_attachment=True,
        filename=f'tasks_{request.user.username}.json',
        content_type='application/json',
    )


@login_required
def export_xml_view(request):
    """Export the current user's tasks as an XML file download."""
    from .export import export_to_xml

    filepath = os.path.join(
        getattr(settings, 'MEDIA_ROOT', 'media'),
        'exports',
        f'tasks_{request.user.username}.xml',
    )
    export_to_xml(filepath=filepath, user=request.user)

    if not os.path.exists(filepath):
        raise Http404("Export file not found.")

    return FileResponse(
        open(filepath, 'rb'),
        as_attachment=True,
        filename=f'tasks_{request.user.username}.xml',
        content_type='application/xml',
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. EDA View
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def eda_view(request):
    """Run EDA pipeline and return statistics + chart URLs as JSON."""
    from .eda import run_full_eda

    output_dir  = os.path.join(getattr(settings, 'MEDIA_ROOT', 'media'), 'eda')
    report_path = os.path.join(output_dir, 'eda_report.json')

    stats = run_full_eda(output_dir=output_dir, report_path=report_path)

    if 'error' in stats:
        return JsonResponse(stats, status=404)

    # Convert local file paths to media URLs for the frontend
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    chart_urls = []
    for path in stats.get('charts_saved', []):
        rel = os.path.relpath(path, getattr(settings, 'MEDIA_ROOT', 'media'))
        chart_urls.append(media_url + rel.replace('\\', '/'))

    stats['chart_urls'] = chart_urls
    stats.pop('charts_saved', None)

    return JsonResponse(stats)
