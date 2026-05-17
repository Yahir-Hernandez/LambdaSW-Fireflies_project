from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Lodging, Park, Reservation, Service
from .services import ReservationService


class LodgingInline(admin.TabularInline):
    model = Lodging
    extra = 0
    fields = ("kind", "name", "capacity", "description")


@admin.register(Park)
class ParkAdmin(admin.ModelAdmin):
    """Gestión de parques con eliminación lógica (RF-09)."""

    list_display = (
        "name",
        "camping_capacity",
        "has_cabins_display",
        "is_deleted",
    )
    list_filter = ("is_deleted",)
    search_fields = ("name", "address")
    filter_horizontal = ("services",)
    inlines = [LodgingInline]
    actions = ["soft_delete_selected", "restore_selected"]

    def get_queryset(self, request):
        # Mostrar también los eliminados en el admin para poder restaurarlos.
        return Park.objects.all()

    def delete_model(self, request, obj):
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        for park in queryset:
            park.soft_delete()

    @admin.display(description="Tiene cabañas", boolean=True)
    def has_cabins_display(self, obj):
        return obj.has_cabins

    @admin.action(description="Eliminar lógicamente los parques seleccionados")
    def soft_delete_selected(self, request, queryset):
        for park in queryset:
            park.soft_delete()
        self.message_user(
            request,
            f"{queryset.count()} parque(s) eliminados lógicamente.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Restaurar los parques seleccionados")
    def restore_selected(self, request, queryset):
        for park in queryset:
            park.restore()
        self.message_user(
            request,
            f"{queryset.count()} parque(s) restaurados.",
            level=messages.SUCCESS,
        )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Lodging)
class LodgingAdmin(admin.ModelAdmin):
    list_display = ("name", "park", "kind", "capacity")
    list_filter = ("kind", "park")
    search_fields = ("name", "park__name")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Vista administrativa de reservaciones (RF-10)."""

    list_display = (
        "id",
        "user",
        "user_email",
        "park",
        "lodging",
        "start_date",
        "duration_days",
        "people",
        "status",
    )
    list_filter = ("status", "lodging__kind", "park")
    search_fields = ("user__username", "user__email", "park__name", "lodging__name")
    actions = ["cancel_reservations"]
    readonly_fields = ("created_at",)

    @admin.display(description="Correo")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Duración (días)")
    def duration_days(self, obj):
        return (obj.end_date - obj.start_date).days

    @admin.action(description="Cancelar las reservaciones seleccionadas")
    def cancel_reservations(self, request, queryset):
        cancelled = 0
        errors = 0
        for reservation in queryset:
            try:
                ReservationService.cancel_reservation(request.user, reservation)
                cancelled += 1
            except ValidationError:
                errors += 1
        if cancelled:
            self.message_user(
                request,
                f"{cancelled} reservación(es) canceladas.",
                level=messages.SUCCESS,
            )
        if errors:
            self.message_user(
                request,
                f"{errors} reservación(es) no pudieron cancelarse.",
                level=messages.WARNING,
            )
