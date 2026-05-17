from collections import defaultdict

from django.db import migrations, models


def consolidate_services(apps, schema_editor):
    """Colapsa los Service per-park en un catálogo global y los reconecta vía M2M."""
    Service = apps.get_model("sistema_app", "Service")
    Park = apps.get_model("sistema_app", "Park")
    # Insertamos en la tabla intermedia M2M directamente porque los managers de
    # relaciones inversas (`park.services.add(...)`) no siempre están disponibles
    # sobre los modelos históricos que Django reconstruye en migraciones.
    Through = Park.services.through

    by_name = defaultdict(list)
    for s in Service.objects.all():
        by_name[s.name].append(s)

    for services in by_name.values():
        kept = services[0]
        park_ids = {s.park_id for s in services if s.park_id is not None}
        for pid in park_ids:
            Through.objects.get_or_create(park_id=pid, service_id=kept.id)
        for s in services[1:]:
            s.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_app", "0002_services_per_park"),
    ]

    operations = [
        migrations.AddField(
            model_name="park",
            name="services",
            field=models.ManyToManyField(
                blank=True,
                related_name="parks",
                to="sistema_app.service",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="service",
            unique_together=set(),
        ),
        migrations.RunPython(consolidate_services, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="service",
            name="park",
        ),
        migrations.AlterField(
            model_name="service",
            name="name",
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterModelOptions(
            name="service",
            options={
                "ordering": ("name",),
                "verbose_name": "Servicio",
                "verbose_name_plural": "Servicios",
            },
        ),
    ]
