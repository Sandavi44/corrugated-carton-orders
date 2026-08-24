from django.core.management.base import BaseCommand

from orders.excel_import import import_orders_from_excel


class Command(BaseCommand):
    help = "Import orders from an existing Excel sheet into the database."

    def add_arguments(self, parser):
        parser.add_argument("excel_path", type=str)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Parse and validate the file without writing to the database.",
        )

    def handle(self, *args, **options):
        stats = import_orders_from_excel(options["excel_path"], dry_run=options["dry_run"])

        if stats["missing_columns"]:
            self.stderr.write(self.style.ERROR(
                f"File is missing required column(s): {', '.join(stats['missing_columns'])}"
            ))
            return

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run complete — nothing was saved."))

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created: {stats['created']}, Skipped: {stats['skipped']}, "
            f"Unparseable dates: {stats['bad_dates']}"
        ))
        rows = stats["skipped_rows"]
        if rows:
            self.stdout.write("Rows needing a look:")
            for idx, reason in rows[:50]:
                self.stdout.write(f"  row {idx}: {reason}")
            if len(rows) > 50:
                self.stdout.write(f"  ...and {len(rows) - 50} more.")
