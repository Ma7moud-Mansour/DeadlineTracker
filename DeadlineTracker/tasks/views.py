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
from google import genai as genai_client





from django.core.cache import cache
from django.http import HttpResponseForbidden
from functools import wraps

def custom_ratelimit(requests_limit=5, timeout=60):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.method == 'POST':
                # بنجيب الـ IP بتاع المستخدم
                ip = request.META.get('REMOTE_ADDR')
                cache_key = f"ratelimit_{ip}_{request.path}"

                # بنشوف بعت كام Request
                request_count = cache.get(cache_key, 0)

                if request_count >= requests_limit:
                    return HttpResponseForbidden("Too many requests. Please try again later.")

                # بنزود الـ Count وبنحفظه في الكاش بالـ Timeout المحدد (مثلاً دقيقة)
                cache.set(cache_key, request_count + 1, timeout)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator



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
@custom_ratelimit(requests_limit=5, timeout=60)  # 5 requests لكل دقيقة
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
        api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return JsonResponse({'error': 'API Key missing'}, status=400)

        client = genai_client.Client(api_key=api_key)

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
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                request.session['roaster_triggered'] = True
                return JsonResponse({'message': response.text})
            
            request.session['roaster_triggered'] = True
            return JsonResponse({'message': None})

        # 2. الـ Plan (تنظيم اليوم) - ده اللي ظهر في الصورة
        elif mode == 'plan':
            tasks = UniversityTask.objects.filter(user=request.user, is_completed=False)
            task_list = "\n".join([f"- {t.title} ({t.course})" for t in tasks])
            prompt = f"بص يا جيمي، دي تاسكاتي، رتبهملي بجدول أولويات صايع بلهجة مصرية شجاعة:\n{task_list}"
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return JsonResponse({'message': response.text})

        # 3. Break (تفكيك التاسك)
        elif mode == 'break':
            task_id = body.get('task_id')
            task    = UniversityTask.objects.get(id=task_id, user=request.user)
            prompt  = (
                f"بسطلي التاسك دي ('{task.title}' من مادة {task.course}) "
                f"لـ ٣ خطوات واضحة تخليني أبدأ فيها فوراً. "
                f"اكتب بلهجة مصرية حماسية وخلي كل خطوة في سطر منفصل."
            )
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return JsonResponse({'message': response.text})

        # 4. Classify (تصنيف كل التاسكات بالأولوية)
        elif mode == 'classify':
            from .features import classify_urgency, compute_urgency_score
            tasks = UniversityTask.objects.filter(user=request.user, is_completed=False)
            classified = [
                {
                    "id":            t.id,
                    "title":         t.title,
                    "course":        t.course,
                    "due_date":      t.due_date,
                    "urgency_label": classify_urgency(t.due_date),
                    "urgency_score": compute_urgency_score(t.due_date),
                }
                for t in tasks
            ]
            # Sort by urgency score descending
            classified.sort(key=lambda x: -x["urgency_score"])

            # Generate AI summary of the classification
            label_summary = ", ".join(
                f"{x['urgency_label']}: {x['title'][:30]}" for x in classified[:5]
            )
            prompt = (
                f"دي أعلى ٥ تاسكات أولوية عند الطالب: {label_summary}. "
                f"قوله بجملتين مصريين سريعين إيه اللي المفروض يعمله دلوقتي."
            )
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

            return JsonResponse({
                'tasks':   classified,
                'message': response.text,
            })

        # 5. Summarize (تلخيص كل التاسكات)
        elif mode == 'summarize':
            tasks     = UniversityTask.objects.filter(user=request.user, is_completed=False)
            task_list = "\n".join(
                f"- {t.title} | {t.course} | {t.due_date}" for t in tasks
            )
            prompt = (
                f"لخصلي الوضع الأكاديمي لطالب عنده التاسكات دي:\n{task_list}\n\n"
                f"اكتب ملخص من ٣ جمل: الوضع العام، أكتر حاجة ضاغطة، ونصيحة واحدة."
                f" بلهجة مصرية واضحة."
            )
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return JsonResponse({'message': response.text})

        # 6. Sentiment (تحليل مزاج الطالب من التاسكات)
        elif mode == 'sentiment':
            from .features import compute_urgency_score
            tasks       = list(UniversityTask.objects.filter(user=request.user, is_completed=False))
            overdue_n   = sum(1 for t in tasks if _parse_due_date(t.due_date) < datetime.now())
            total_n     = len(tasks)
            avg_urgency = round(
                sum(compute_urgency_score(t.due_date) for t in tasks) / max(total_n, 1), 1
            )
            titles = ", ".join(t.title[:40] for t in tasks[:6])
            prompt = (
                f"الطالب عنده {total_n} تاسك، منهم {overdue_n} فاتوا ميعادهم، "
                f"ومتوسط الضغط {avg_urgency}/100. "
                f"أسماء بعض التاسكات: {titles}. "
                f"حلل الوضع النفسي والأكاديمي بتاعه في جملتين، وقوله حاجة تشجعه."
                f" اكتب بالعربي."
            )
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return JsonResponse({
                'message':     response.text,
                'stats': {
                    'total':       total_n,
                    'overdue':     overdue_n,
                    'avg_urgency': avg_urgency,
                },
            })

        return JsonResponse({'error': 'Unknown mode'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Feature Extraction View
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def features_view(request):
    """Return extracted features for the current user's pending tasks."""
    from .features import enrich_tasks, compute_tfidf, compute_workload_index

    qs    = UniversityTask.objects.filter(user=request.user, is_completed=False)
    tasks = [
        {"id": t.id, "title": t.title, "course": t.course, "due_date": t.due_date}
        for t in qs
    ]

    enriched  = enrich_tasks(tasks)
    tfidf     = compute_tfidf(tasks)
    workload  = compute_workload_index(tasks)

    return JsonResponse({
        "total_tasks": len(tasks),
        "tasks":       enriched,
        "tfidf":       tfidf,
        "workload_index": workload,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 8. Evaluation View
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def evaluation_view(request):
    """Run full evaluation report on the current user's tasks."""
    from .evaluation import generate_evaluation_report, evaluate_ai_response

    qs    = UniversityTask.objects.filter(user=request.user)
    tasks = [
        {"title": t.title, "course": t.course, "due_date": t.due_date,
         "is_completed": t.is_completed}
        for t in qs
    ]

    report = generate_evaluation_report(tasks)

    # Sample AI response quality check (using last known AI response if passed)
    sample_text = request.GET.get("sample_response", "")
    if sample_text:
        report["ai_response_quality"] = evaluate_ai_response(sample_text)

    return JsonResponse(report)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Search View (TF-IDF keyword search)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def search_view(request):
    """Search the user's tasks by keyword using TF-IDF relevance ranking."""
    from .features import search_tasks

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"error": "Missing query parameter ?q="}, status=400)

    qs    = UniversityTask.objects.filter(user=request.user, is_completed=False)
    tasks = [
        {"id": t.id, "title": t.title, "course": t.course, "due_date": t.due_date}
        for t in qs
    ]

    hits = search_tasks(tasks, query, top_n=10)
    results = [
        {**tasks[i], "relevance_score": score}
        for i, score in hits
    ]

    return JsonResponse({"query": query, "results": results, "count": len(results)})