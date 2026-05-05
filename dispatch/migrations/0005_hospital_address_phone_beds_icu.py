from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dispatch", "0004_seed_demo_hospital_driver_and_admin_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospital",
            name="address",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="hospital",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="hospital",
            name="bed_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="hospital",
            name="icu_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
