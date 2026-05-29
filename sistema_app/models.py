"""Modelos del dominio del festival: parques, hospedajes, reservas y seguridad."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Service(models.Model):
    """Servicio del catálogo que puede asociarse a varios parques.

    Cada servicio existe una sola vez y los parques lo enlazan mediante
    una relación de muchos a muchos.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ("name",)

    def __str__(self):
        return self.name


class ParkQuerySet(models.QuerySet):
    """Conjunto de consultas personalizadas para el modelo Park."""

    def active(self):
        """Devuelve únicamente los parques que no han sido eliminados."""
        return self.filter(is_deleted=False)


class Park(models.Model):
    """Parque del festival con su ubicación, contacto y servicios disponibles.

    Los parques se borran de forma lógica con soft_delete para no romper
    la integridad de las reservas asociadas.
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
        """
        Marca el parque como eliminado sin borrarlo de la base de datos.

        Raises:
            ValidationError: Si el parque tiene reservaciones activas.
        """
        if self.reservations.filter(status=Reservation.Status.ACTIVE).exists():
            raise ValidationError(
                "No se puede eliminar un parque con reservaciones activas."
            )
        if not self.is_deleted:
            self.is_deleted = True
            self.save(update_fields=["is_deleted"])

    def restore(self):
        """Reactiva un parque previamente marcado como eliminado."""
        if self.is_deleted:
            self.is_deleted = False
            self.save(update_fields=["is_deleted"])

    @property
    def has_cabins(self) -> bool:
        """Indica si el parque tiene al menos una cabaña registrada."""
        return self.lodgings.filter(kind=Lodging.Kind.CABIN).exists()

    @property
    def camping_capacity(self) -> int:
        """Devuelve la suma de la capacidad de todas las parcelas de camping del parque."""
        total = self.lodgings.filter(kind=Lodging.Kind.CAMPING).aggregate(
            total=models.Sum("capacity")
        )["total"]
        return total or 0

    def __str__(self):
        return self.name


class Lodging(models.Model):
    """Unidad de hospedaje reservable dentro de un parque.

    Puede ser una cabaña, que es de uso exclusivo, o una parcela de
    camping, que se comparte entre varias reservas mientras la suma de
    personas no supere su capacidad.
    """

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
        """Valida que la capacidad no se reduzca por debajo de las reservas existentes."""
        super().clean()
        from .services.lodging_validation import LodgingCapacityValidator
        LodgingCapacityValidator.validate_capacity_reduction(self, self.capacity)


class Reservation(models.Model):
    """Reservación realizada por un usuario sobre un hospedaje en un rango de fechas."""

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

    # Identificador único usado para construir el código QR de check-in.
    # Se genera al crear la reserva y no vuelve a cambiar.
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
        """Indica si la reservación puede cancelarse desde el perfil del usuario."""
        return (
            self.status == self.Status.ACTIVE
            and self.start_date > timezone.localdate()
        )

    def mark_as_used(self) -> None:
        """
        Marca la reservación como consumida tras un check-in exitoso.

        Raises:
            ValidationError: Si la reservación no está en estado activa
                porque ya fue usada, cancelada o pasada.
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
    """Registro temporal de un usuario que todavía no ha verificado su correo.

    El usuario real recién se crea en la tabla de usuarios cuando el
    código de verificación se valida con éxito. Esto evita que alguien
    reserve nombres de usuario sin completar el alta y mantiene la tabla
    de usuarios libre de cuentas inactivas.
    """

    EXPIRY_SECONDS = 300  # cinco minutos
    RESEND_COOLDOWN_SECONDS = 120  # dos minutos

    username = models.CharField(max_length=150)
    email = models.EmailField()
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    # Ya viene en formato hash, no en texto plano.
    password = models.CharField(max_length=128)
    code = models.CharField(max_length=5)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Registro pendiente"
        verbose_name_plural = "Registros pendientes"

    def seconds_elapsed(self) -> int:
        """Devuelve los segundos transcurridos desde que se inició el registro."""
        return int((timezone.now() - self.created_at).total_seconds())

    def is_expired(self) -> bool:
        """Indica si el registro ya superó el tiempo máximo permitido."""
        return self.seconds_elapsed() > self.EXPIRY_SECONDS

    def seconds_until_resend(self) -> int:
        """Devuelve cuántos segundos faltan para poder reenviar el código."""
        return max(0, self.RESEND_COOLDOWN_SECONDS - self.seconds_elapsed())


class LoginAttempt(models.Model):
    """Bitácora de intentos de inicio de sesión para bloquear cuentas tras varios fallos."""

    MAX_FAILED_ATTEMPTS = 6
    LOCKOUT_WINDOW_SECONDS = 900  # quince minutos

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
        """
        Indica si el usuario quedó bloqueado por demasiados intentos fallidos.

        Args:
            username: Nombre de usuario a consultar.

        Returns:
            True si el usuario acumuló al menos MAX_FAILED_ATTEMPTS
            intentos fallidos dentro de la ventana de tiempo configurada.
        """
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
        """Guarda un intento de inicio de sesión asociado al nombre de usuario dado."""
        if username:
            cls.objects.create(username=username, success=success)

    def __str__(self) -> str:
        estado = "éxito" if self.success else "fallo"
        return f"{self.username} · {estado} · {self.attempted_at:%Y-%m-%d %H:%M}"


class PasswordResetToken(models.Model):
    """Token de un solo uso para restablecer la contraseña por correo.

    El flujo es:
    1. El usuario solicita el restablecimiento → se genera un token y se envía
       por correo como código numérico de 6 dígitos.
    2. El usuario ingresa el código en la página de verificación.
    3. Una vez verificado se marca ``is_verified=True`` y se permite elegir
       una nueva contraseña.
    4. Tras usarse o expirar, el token queda inútil.
    """

    EXPIRY_SECONDS = 600       # 10 minutos
    RESEND_COOLDOWN_SECONDS = 120

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Token de restablecimiento de contraseña"
        verbose_name_plural = "Tokens de restablecimiento de contraseña"
        ordering = ("-created_at",)

    def is_expired(self) -> bool:
        """Indica si el token ya superó el tiempo máximo permitido."""
        return (timezone.now() - self.created_at).total_seconds() > self.EXPIRY_SECONDS

    def seconds_until_resend(self) -> int:
        """Segundos que faltan para poder reenviar el código."""
        elapsed = int((timezone.now() - self.created_at).total_seconds())
        return max(0, self.RESEND_COOLDOWN_SECONDS - elapsed)

    def __str__(self) -> str:
        return f"Reset token para {self.user.username} · {self.created_at:%Y-%m-%d %H:%M}"