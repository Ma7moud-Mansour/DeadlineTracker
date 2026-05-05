"""
Django management command to run the EDA pipeline.

Usage:
    python manage.py run_eda
    python manage.py run_eda --output-dir media/eda --report media/eda/eda_report.json
"""

import json
from django.core.management.base import BaseCommand
from tasks.eda import run_full_eda


class Command(BaseCommand):
    help = "Run EDA pipeline: compute statistics, generate charts, save JSON report"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="media/eda",
            help="Directory to save chart PNG files (default: media/eda)",
        )
        parser.add_argument(
            "--report",
            default="media/eda/eda_report.json",
            help="Path to write the JSON statistics report",
        )

    def handle(self, *args, **options):
        self.stdout.write("Running EDA pipeline...")

        stats = run_full_eda(
            output_dir=options["output_dir"],
            report_path=options["report"],
        )

        if "error" in stats:
            self.stderr.write(self.style.ERROR(f"EDA failed: {stats['error']}"))
            return

        self.stdout.write(self.style.SUCCESS("\n=== EDA Complete ==="))
        self.stdout.write(f"  Total tasks   : {stats['total_tasks']}")
        self.stdout.write(f"  Total users   : {stats['total_users']}")
        self.stdout.write(f"  Completed     : {stats['completed']}")
        self.stdout.write(f"  Pending       : {stats['pending']}")
        self.stdout.write(f"  Completion %  : {stats['completion_rate_pct']}%")
        self.stdout.write(f"  Unique courses: {stats['unique_courses']}")
        self.stdout.write(f"  Charts saved  : {len(stats.get('charts_saved', []))}")
        self.stdout.write(f"  Report        : {options['report']}")
        self.stdout.write("\nTop courses:")
        for entry in stats.get("top_courses", [])[:5]:
            self.stdout.write(f"    {entry['course'][:50]:<50}  {entry['count']} tasks")
