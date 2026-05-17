import os
import json
from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings

from .models import UniversityTask
from .scraper import run_msa_scraper
import google.generativeai as genai




def _parse_due_date(date_str):
    """Parse a due_date CharField into a datetime.
    Handles multiple formats found in the DB:
      - 'Monday, 27 April 2026 - 23:59'  (Moodle human-readable)
      - '2026-04-22 15:15:00'             (ISO-like)
    Returns datetime.max on failure so unparseable dates sort last."""
    if not date_str:
        return datetime.max

    # Format 1: ISO-like  "2026-04-22 15:15:00"
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    # Format 2: Moodle human-readable  "Monday, 27 April 2026 - 23:59"
    try:
        clean = date_str.split(',', 1)[-1].strip() if ',' in date_str else date_str
        clean = clean.replace(' - ', ' ')
        return datetime.strptime(clean, '%d %B %Y %H:%M')
    except (ValueError, AttributeError):
        pass

    return datetime.max


# ─────────────────────────────────────────────────────────────────────────────
# 1. Sync / Login View
# ─────────────────────────────────────────────────────────────────────────────
from ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
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
    )

    # ── Course filtering ──────────────────────────────────────────────────
    all_courses = (
        tasks.values_list('course', flat=True)
        .distinct()
        .order_by('course')
    )
    selected_course = request.GET.get('course', '')
    if selected_course:
        tasks = tasks.filter(course=selected_course)

    # ── Sorting ───────────────────────────────────────────────────────────
    sort = request.GET.get('sort', 'date_asc')

    if sort in ('date_asc', 'date_desc'):
        # Python-level sort: parse the CharField into real datetimes
        tasks = sorted(
            tasks,
            key=lambda t: _parse_due_date(t.due_date),
            reverse=(sort == 'date_desc'),
        )
    else:
        db_sort_map = {
            'title_asc':  'title',
            'title_desc': '-title',
            'course_asc': 'course',
            'course_desc':'-course',
        }
        tasks = tasks.order_by(db_sort_map.get(sort, 'title'))

    context = {
        'tasks': tasks,
        'all_courses': all_courses,
        'selected_course': selected_course,
        'current_sort': sort,
    }
    return render(request, 'tasks/task_list.html', context)


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


# ─────────────────────────────────────────────────────────────────────────────
# 6. AI Assistant
# ─────────────────────────────────────────────────────────────────────────────




@login_required
def process_ai_request(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             return JsonResponse({'error': 'API Key missing'}, status=400)
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        body = json.loads(request.body)
        mode = body.get('mode')

        # 1. الـ Roaster (التهزيق اللطيف)
        if mode == 'roaster':
            if request.session.get('roaster_triggered'):
                return JsonResponse({'message': None})
            
            tasks = UniversityTask.objects.filter(user=request.user, is_completed=False)
            now = datetime.now()
            missed_tasks = [t.title for t in tasks if _parse_due_date(t.due_date) < now]
            
            if missed_tasks:
                prompt = f"إنت مرشد أكاديمي مصري بتهزأ الطالب عشان ساب التاسكات دي: {', '.join(missed_tasks)}. شرشحله بلهجة مصرية مضحكة واستخدم 'يا فاشل' و 'يا حودة' بس حفزه في الآخر."
                response = model.generate_content(prompt)
                request.session['roaster_triggered'] = True
                return JsonResponse({'message': response.text})
            
            request.session['roaster_triggered'] = True
            return JsonResponse({'message': None})

        # 2. الـ Plan (تنظيم اليوم) - ده اللي ظهر في الصورة
        elif mode == 'plan':
            tasks = UniversityTask.objects.filter(user=request.user, is_completed=False)
            task_list = "\n".join([f"- {t.title} ({t.course})" for t in tasks])
            prompt = f"بص يا جيمي، دي تاسكاتي، رتبهملي بجدول أولويات صايع بلهجة مصرية شجاعة:\n{task_list}"
            response = model.generate_content(prompt)
            return JsonResponse({'message': response.text})

        # 3. الـ Break (تفكيك التاسك)
        elif mode == 'break':
            task_id = body.get('task_id')
            task = UniversityTask.objects.get(id=task_id, user=request.user)
            prompt = f"بسطلي التاسك دي ('{task.title}') لـ ٣ خطوات تافهة تخليني أبدأ بلهجة مصرية حماسية."
            response = model.generate_content(prompt)
            return JsonResponse({'message': response.text})

        # لو مبعت مـود غريب
        return JsonResponse({'error': 'Unknown mode'}, status=400)
        
    except Exception as e:
        print(f"CRITICAL AI ERROR: {str(e)}") 
        return JsonResponse({'error': str(e)}, status=500)