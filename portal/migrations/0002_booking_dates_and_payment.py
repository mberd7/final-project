"""Bookings get real dates (start/end) and a status, and payments get their own table.

Existing rentals are converted: start = the day it was created, end = start + days - 1.
"""
from datetime import timedelta

import django.db.models.deletion
from django.db import migrations, models


def days_to_dates(apps, schema_editor):
    Rental = apps.get_model("portal", "Rental")
    for rental in Rental.objects.all():
        rental.start_date = rental.created_at.date()
        rental.end_date = rental.start_date + timedelta(days=max(rental.days, 1) - 1)
        rental.save(update_fields=["start_date", "end_date"])


def dates_to_days(apps, schema_editor):
    Rental = apps.get_model("portal", "Rental")
    for rental in Rental.objects.all():
        rental.days = (rental.end_date - rental.start_date).days + 1
        rental.save(update_fields=["days"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="rental",
            name="start_date",
            field=models.DateField(null=True, verbose_name="აყვანის თარიღი"),
        ),
        migrations.AddField(
            model_name="rental",
            name="end_date",
            field=models.DateField(null=True, verbose_name="დაბრუნების თარიღი"),
        ),
        migrations.AlterField(
            model_name="rental",
            name="days",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="დღეები"),
        ),
        migrations.RunPython(days_to_dates, dates_to_days),
        migrations.AlterField(
            model_name="rental",
            name="start_date",
            field=models.DateField(verbose_name="აყვანის თარიღი"),
        ),
        migrations.AlterField(
            model_name="rental",
            name="end_date",
            field=models.DateField(verbose_name="დაბრუნების თარიღი"),
        ),
        migrations.RemoveField(model_name="rental", name="days"),
        migrations.AddField(
            model_name="rental",
            name="status",
            field=models.CharField(
                choices=[("paid", "გადახდილი"), ("cancelled", "გაუქმებული")],
                default="paid", max_length=20, verbose_name="სტატუსი",
            ),
        ),
        migrations.AlterField(
            model_name="rental",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="შექმნის დრო"),
        ),
        migrations.AlterModelOptions(
            name="rental",
            options={
                "ordering": ["-start_date", "-created_at"],
                "verbose_name": "ჯავშანი",
                "verbose_name_plural": "ჯავშნები",
            },
        ),
        migrations.AddConstraint(
            model_name="rental",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_date__gte", models.F("start_date"))),
                name="rental_end_after_start",
            ),
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.PositiveIntegerField(verbose_name="თანხა (₾)")),
                ("cardholder", models.CharField(max_length=100, verbose_name="ბარათის მფლობელი")),
                ("card_brand", models.CharField(max_length=20, verbose_name="ბარათის ტიპი")),
                ("card_last4", models.CharField(max_length=4, verbose_name="ბოლო 4 ციფრი")),
                ("status", models.CharField(
                    choices=[("paid", "გადახდილი"), ("refunded", "დაბრუნებული")],
                    default="paid", max_length=20, verbose_name="სტატუსი",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="გადახდის დრო")),
                ("rental", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="payment", to="portal.rental",
                )),
            ],
            options={"verbose_name": "გადახდა", "verbose_name_plural": "გადახდები"},
        ),
    ]
