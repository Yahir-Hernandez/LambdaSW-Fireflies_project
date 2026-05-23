import django.db.models.deletion
from django.db import migrations, models


def seed_camping_lodgings(apps, schema_editor):
    """Crea Lodgings de tipo CAMPING a partir del antiguo Park.camping_capacity y
    asigna las reservaciones de camping existentes a ese nuevo Lodging.
    """
    Park = apps.get_model("sistema_app", "Park")
    Lodging = apps.get_model("sistema_app", "Lodging")
    Reservation = apps.get_model("sistema_app", "Reservation")

    for park in Park.objects.all():
        if park.camping_capacity and park.camping_capacity > 0:
            Lodging.objects.get_or_create(
                park=park,
                name="Parcela general",
                defaults={
                    "kind": "CAMPING",
                    "capacity": park.camping_capacity,
                    "description": (
                        "Migrado desde el cupo agregado de camping. "
                        "Recomendado: subdividir en parcelas individuales."
                    ),
                },
            )

    for reservation in Reservation.objects.filter(lodging__isnull=True):
        camping = Lodging.objects.filter(park_id=reservation.park_id, kind="CAMPING").first()
        if camping is None:
            camping = Lodging.objects.create(
                park_id=reservation.park_id,
                kind="CAMPING",
                name="Parcela general",
                capacity=max(reservation.people, 1),
            )
        reservation.lodging = camping
        reservation.save(update_fields=["lodging"])


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_app", "0003_services_global"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Cabin",
            new_name="Lodging",
        ),
        migrations.AlterModelOptions(
            name="lodging",
            options={
                "ordering": ("kind", "name"),
                "verbose_name": "Hospedaje",
                "verbose_name_plural": "Hospedajes",
            },
        ),
        migrations.AddField(
            model_name="lodging",
            name="kind",
            field=models.CharField(
                choices=[("CABIN", "Cabaña"), ("CAMPING", "Parcela de camping")],
                default="CABIN",
                max_length=10,
            ),
        ),
        migrations.RenameField(
            model_name="reservation",
            old_name="cabin",
            new_name="lodging",
        ),
        migrations.RunPython(seed_camping_lodgings, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="lodging",
            name="kind",
            field=models.CharField(
                choices=[("CABIN", "Cabaña"), ("CAMPING", "Parcela de camping")],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="lodging",
            name="park",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lodgings",
                to="sistema_app.park",
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="lodging",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservations",
                to="sistema_app.lodging",
            ),
        ),
        migrations.RemoveIndex(
            model_name="reservation",
            name="sistema_app_park_id_0b09f4_idx",
        ),
        migrations.RemoveField(
            model_name="reservation",
            name="visit_type",
        ),
        migrations.RemoveField(
            model_name="park",
            name="camping_capacity",
        ),
        migrations.RemoveField(
            model_name="park",
            name="has_cabins",
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(fields=["park", "status"], name="sistema_app_park_id_90f926_idx"),
        ),
    ]
