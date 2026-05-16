import django.db.models.deletion
from django.db import migrations, models


def m2m_to_fk(apps, schema_editor):
    Service = apps.get_model("sistema_app", "Service")
    Park = apps.get_model("sistema_app", "Park")
    Through = Park.services.through

    pairs = list(Through.objects.values_list("park_id", "service_id"))
    services_meta = {s.id: (s.name, s.description) for s in Service.objects.all()}

    for park_id, service_id in pairs:
        meta = services_meta.get(service_id)
        if meta is None:
            continue
        name, description = meta
        Service.objects.create(park_id=park_id, name=name, description=description)

    Service.objects.filter(park__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_app", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AddField(
            model_name="service",
            name="park",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="park_services_tmp",
                to="sistema_app.park",
            ),
        ),
        migrations.RunPython(m2m_to_fk, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="park",
            name="services",
        ),
        migrations.AlterField(
            model_name="service",
            name="park",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="services",
                to="sistema_app.park",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="service",
            unique_together={("park", "name")},
        ),
    ]
