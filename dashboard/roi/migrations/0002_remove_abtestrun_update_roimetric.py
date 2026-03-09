from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("roi", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ABTestRun",
        ),
        migrations.AlterField(
            model_name="roimetric",
            name="model_version",
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name="roimetric",
            name="period",
            field=models.CharField(max_length=40),
        ),
    ]
