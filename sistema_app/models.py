from django.conf import settings
from django.db import models
from django.utils import timezone


class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"

    def __str__(self):
        return self.name


class ParkQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)


class Park(models.Model):
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    camping_capacity = models.PositiveIntegerField(default=0)
    has_cabins = models.BooleanField(default=False)

    working_hours = models.CharField(max_length=120, blank=True)
    services = models.ManyToManyField(Service, blank=True, related_name="parks")

    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    is_deleted = models.BooleanField(default=False)

    objects = ParkQuerySet.as_manager()

    class Meta:
        verbose_name = "Parque"
        verbose_name_plural = "Parques"

    def soft_delete(self):
        if not self.is_deleted:
            self.is_deleted = True
            self.save(update_fields=["is_deleted"])

    def restore(self):
        if self.is_deleted:
            self.is_deleted = False
            self.save(update_fields=["is_deleted"])

    def __str__(self):
        return self.name


class Cabin(models.Model):
    park = models.ForeignKey(Park, on_delete=models.CASCADE, related_name="cabins")
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Cabaña"
        verbose_name_plural = "Cabañas"
        unique_together = ("park", "name")

    def __str__(self):
        return f"{self.park.name} · {self.name}"


class Reservation(models.Model):
    class VisitType(models.TextChoices):
        CAMPING = "CAMPING", "Camping"
        CABIN = "CABIN", "Cabaña"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activa"
        CANCELLED = "CANCELLED", "Cancelada"
        PAST = "PAST", "Pasada"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    park = models.ForeignKey(Park, on_delete=models.PROTECT, related_name="reservations")
    cabin = models.ForeignKey(
        Cabin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reservations",
    )
    visit_type = models.CharField(max_length=10, choices=VisitType.choices)

    start_date = models.DateField()
    end_date = models.DateField()
    people = models.PositiveIntegerField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reservación"
        verbose_name_plural = "Reservaciones"
        ordering = ("-start_date",)
        indexes = [
            models.Index(fields=["park", "visit_type", "status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def is_cancellable(self) -> bool:
        return (
            self.status == self.Status.ACTIVE
            and self.start_date > timezone.localdate()
        )

    def __str__(self):
        return f"Reservación #{self.pk} · {self.user} · {self.park.name}"
