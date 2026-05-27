import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Service(models.Model):
    """Catálogo global cuyos elementos pueden
     ser asociados a un parque con una relación n:m"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ("name",)

    def __str__(self):
        return self.name


class ParkQuerySet(models.QuerySet):
    """
    Retorna todos los parques activos actualmente.
    """
    def active(self):
        return self.filter(is_deleted=False)


class Park(models.Model):
    """
    Modelo que representa a un parque con todos sus atributos.
    """
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=300)
    description = models.TextField(blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

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
        if self.reservations.filter(status=Reservation.Status.ACTIVE).exists():
            raise ValidationError(
                "No se puede eliminar un parque con reservaciones activas."
            )
        if not self.is_deleted:
            self.is_deleted = True
            self.save(update_fields=["is_deleted"])

    def restore(self):
        if self.is_deleted:
            self.is_deleted = False
            self.save(update_fields=["is_deleted"])

    @property
    def has_cabins(self) -> bool:
        return self.lodgings.filter(kind=Lodging.Kind.CABIN).exists()

    @property
    def camping_capacity(self) -> int:
        total = self.lodgings.filter(kind=Lodging.Kind.CAMPING).aggregate(
            total=models.Sum("capacity")
        )["total"]
        return total or 0

    def __str__(self):
        return self.name


class Lodging(models.Model):
    """Unidad de hospedaje reservable. Una cabaña o una parcela de camping."""

    class Kind(models.TextChoices):
        CABIN = "CABIN", "Cabaña"
        CAMPING = "CAMPING", "Parcela de camping"

    park = models.ForeignKey(Park, on_delete=models.CASCADE, related_name="lodgings")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Hospedaje"
        verbose_name_plural = "Hospedajes"
        unique_together = ("park", "name")
        ordering = ("kind", "name")

    def __str__(self):
        return f"{self.park.name} · {self.get_kind_display()}: {self.name}"

    def clean(self):
        super().clean()
        from .services.lodging_validation import LodgingCapacityValidator
        LodgingCapacityValidator.validate_capacity_reduction(self, self.capacity)


class Reservation(models.Model):
    """
    Modelo que representa a una reservación de un cliente.
    """
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activa"
        CANCELLED = "CANCELLED", "Cancelada"
        PAST = "PAST", "Pasada"
        USED = "USED", "Usada"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    park = models.ForeignKey(Park, on_delete=models.PROTECT, related_name="reservations")
    lodging = models.ForeignKey(
        Lodging,
        on_delete=models.PROTECT,
        related_name="reservations",
    )

    start_date = models.DateField()
    end_date = models.DateField()
    people = models.PositiveIntegerField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Token único usado para construir el QR de check-in.
    # Se genera automáticamente y nunca cambia tras la creación.
    checkin_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
    )

    class Meta:
        verbose_name = "Reservación"
        verbose_name_plural = "Reservaciones"
        ordering = ("-start_date",)
        indexes = [
            models.Index(fields=["park", "status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def is_cancellable(self) -> bool:
        return (
            self.status == self.Status.ACTIVE
            and self.start_date > timezone.localdate()
        )

    def mark_as_used(self) -> None:
        """Marca la reserva como consumida tras un check-in exitoso.

        Raises
        ------
        ValidationError
            Si la reserva no está ACTIVE (ya usada, cancelada o pasada).
        """
        if self.status != self.Status.ACTIVE:
            raise ValidationError(
                f"No se puede marcar como usada una reserva en estado "
                f"{self.get_status_display()}."
            )
        self.status = self.Status.USED
        self.save(update_fields=["status"])

    def __str__(self):
        return f"Reservación #{self.pk} · {self.user} · {self.park.name}"


class PendingRegistration(models.Model):
    """Registro de un usuario que aún NO ha verificado su correo.

    No existe en la tabla User hasta que el código se valida con éxito.
    Esto evita squatting de usernames y polución de la BD con cuentas
    inactivas.
    """

    EXPIRY_SECONDS = 300       # 5 minutos
    RESEND_COOLDOWN_SECONDS = 120  # 2 minutos

    username = models.CharField(max_length=150)
    email = models.EmailField()
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    password = models.CharField(max_length=128)  # ya hasheada
    code = models.CharField(max_length=5)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Registro pendiente"
        verbose_name_plural = "Registros pendientes"

    def seconds_elapsed(self) -> int:
        return int((timezone.now() - self.created_at).total_seconds())

    def is_expired(self) -> bool:
        return self.seconds_elapsed() > self.EXPIRY_SECONDS

    def seconds_until_resend(self) -> int:
        return max(0, self.RESEND_COOLDOWN_SECONDS - self.seconds_elapsed())


class LoginAttempt(models.Model):
    """Registro de intentos de login para implementar bloqueo tras N fallos.
    """

    MAX_FAILED_ATTEMPTS = 6
    LOCKOUT_WINDOW_SECONDS = 900  # 15 minutos

    username = models.CharField(max_length=150, db_index=True)
    attempted_at = models.DateTimeField(default=timezone.now, db_index=True)
    success = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Intento de inicio de sesión"
        verbose_name_plural = "Intentos de inicio de sesión"
        ordering = ("-attempted_at",)
        indexes = [
            models.Index(fields=["username", "attempted_at"]),
        ]

    @classmethod
    def is_locked_out(cls, username: str) -> bool:
        if not username:
            return False
        since = timezone.now() - timedelta(seconds=cls.LOCKOUT_WINDOW_SECONDS)
        return (
            cls.objects.filter(
                username=username,
                success=False,
                attempted_at__gte=since,
            ).count()
            >= cls.MAX_FAILED_ATTEMPTS
        )

    @classmethod
    def register(cls, username: str, success: bool) -> None:
        if username:
            cls.objects.create(username=username, success=success)

    def __str__(self) -> str:
        estado = "éxito" if self.success else "fallo"
        return f"{self.username} · {estado} · {self.attempted_at:%Y-%m-%d %H:%M}"
