from datetime import date

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .forms import CustomUserCreationForm
from .models import Lodging, LoginAttempt, Park, PendingRegistration, Reservation
from .services import (
    AvailabilityService,
    NotificationService,
    ReservationService,
    generate_verification_code,
    mask_email,
)


def home(request):
    parques = list(Park.objects.active().prefetch_related("lodgings"))
    today = date.today()
    for parque in parques:
        camping_lodgings = parque.lodgings.filter(kind=Lodging.Kind.CAMPING)
        total = camping_lodgings.aggregate(total=Sum("capacity"))["total"] or 0
        used = (
            Reservation.objects.filter(
                lodging__in=camping_lodgings,
                status=Reservation.Status.ACTIVE,
                end_date__gte=today,
            ).aggregate(total=Sum("people"))["total"]
            or 0
        )
        parque.disponibilidad_actual = max(total - used, 0)
    featured_parks = parques[:3]
    featured_park = featured_parks[0] if featured_parks else None
    total_parks = len(parques)
    lodging_parks = sum(1 for parque in parques if parque.lodgings.all())
    return render(
        request,
        "home.html",
        {
            "featured_parks": featured_parks,
            "featured_park": featured_park,
            "total_parks": total_parks,
            "lodging_parks": lodging_parks,
        },
    )


def festival(request):
    return render(request, "festival.html")


def _safe_next(request, fallback="sistema_app:home"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return resolve_url(fallback)


PENDING_REGISTRATION_KEY = "pending_registration_id"


def _send_pending_code(pending: PendingRegistration) -> None:
    NotificationService.send_verification_email(
        recipient_email=pending.email,
        code=pending.code,
        recipient_name=pending.username,
    )


def register(request):
    data = {"form": CustomUserCreationForm(), "next": request.GET.get("next", "")}
    if request.method == "POST":
        formulario = CustomUserCreationForm(data=request.POST)
        if formulario.is_valid():
            cleaned = formulario.cleaned_data
            # Sólo limpiamos registros pendientes ya EXPIRADOS — los activos
            # los rechaza el formulario (ver CustomUserCreationForm.clean_*).
            # Esto permite que un usuario que perdió su código reintente tras
            # los 5 min de expiración.
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(
                seconds=PendingRegistration.EXPIRY_SECONDS
            )
            PendingRegistration.objects.filter(
                Q(username=cleaned["username"]) | Q(email=cleaned["email"]),
                created_at__lt=cutoff,
            ).delete()
            pending = PendingRegistration.objects.create(
                username=cleaned["username"],
                email=cleaned["email"],
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
                password=make_password(cleaned["password1"]),
                code=generate_verification_code(),
            )
            _send_pending_code(pending)
            request.session[PENDING_REGISTRATION_KEY] = pending.pk
            return redirect("sistema_app:verify_email")
        data["form"] = formulario
    return render(request, "registration/sign_up.html", data)


def _get_pending(request):
    pending_id = request.session.get(PENDING_REGISTRATION_KEY)
    if not pending_id:
        return None
    pending = PendingRegistration.objects.filter(pk=pending_id).first()
    if not pending:
        request.session.pop(PENDING_REGISTRATION_KEY, None)
    return pending


def verify_email_page(request):
    pending = _get_pending(request)
    if not pending:
        return redirect("sistema_app:register")
    return render(
        request,
        "registration/verify_email.html",
        {
            "masked_email": mask_email(pending.email),
            "resend_in": pending.seconds_until_resend(),
        },
    )


@require_POST
def verify_email_api(request):
    pending = _get_pending(request)
    if not pending:
        return JsonResponse(
            {"error": "Tu sesión de verificación expiró. Regístrate nuevamente."},
            status=400,
        )

    code = (request.POST.get("code") or "").strip()
    if not code:
        return JsonResponse({"error": "Ingresa el código que recibiste por correo."}, status=400)
    if pending.is_expired():
        pending.delete()
        request.session.pop(PENDING_REGISTRATION_KEY, None)
        return JsonResponse({"error": "El código expiró. Regístrate nuevamente."}, status=400)
    if pending.code != code:
        return JsonResponse({"error": "Código incorrecto."}, status=400)

    # Defensa contra carreras: alguien pudo haber tomado el username/email
    # entre el signup y la verificación.
    with transaction.atomic():
        if User.objects.filter(username__iexact=pending.username).exists():
            return JsonResponse({"error": "El nombre de usuario ya está tomado."}, status=409)
        if User.objects.filter(email__iexact=pending.email).exists():
            return JsonResponse({"error": "Ya existe una cuenta con ese correo."}, status=409)
        user = User(
            username=pending.username,
            email=pending.email,
            first_name=pending.first_name,
            last_name=pending.last_name,
            is_active=True,
        )
        user.password = pending.password  # ya hasheada
        user.save()
        pending.delete()

    auth_login(request, user)
    request.session.pop(PENDING_REGISTRATION_KEY, None)
    return JsonResponse({"ok": True})


@require_POST
def resend_verification_code_api(request):
    pending = _get_pending(request)
    if not pending:
        return JsonResponse(
            {"error": "Tu sesión de verificación expiró. Regístrate nuevamente."},
            status=400,
        )

    remaining = pending.seconds_until_resend()
    if remaining > 0:
        return JsonResponse(
            {"error": f"Espera {remaining} segundos para reenviar.", "retry_in": remaining},
            status=429,
        )

    pending.code = generate_verification_code()
    pending.created_at = timezone.now()
    pending.save(update_fields=["code", "created_at"])
    _send_pending_code(pending)
    return JsonResponse({"ok": True, "masked_email": mask_email(pending.email)})


def login(request):
    data = {
        "form": AuthenticationForm(),
        "next": request.GET.get("next", ""),
        "lockout": False,
    }
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        if LoginAttempt.is_locked_out(username):
            data["lockout"] = True
            data["form"] = AuthenticationForm(data=request.POST)
            return render(request, "registration/login.html", data)

        formulario = AuthenticationForm(data=request.POST)
        if formulario.is_valid():
            user = authenticate(
                username=formulario.cleaned_data["username"],
                password=formulario.cleaned_data["password"],
            )
            if user is not None:
                LoginAttempt.register(username, success=True)
                auth_login(request, user)
                return redirect(_safe_next(request))
            LoginAttempt.register(username, success=False)
        elif username:
            LoginAttempt.register(username, success=False)
        data["form"] = formulario
    return render(request, "registration/login.html", data)


def logout_view(request):
    logout(request)
    return redirect(to="sistema_app:home")


def mapa(request):
    parques = list(
        Park.objects.active().prefetch_related("services", "lodgings")
    )
    today = date.today()
    for parque in parques:
        camping_lodgings = parque.lodgings.filter(kind=Lodging.Kind.CAMPING)
        total = camping_lodgings.aggregate(total=Sum("capacity"))["total"] or 0
        used = (
            Reservation.objects.filter(
                lodging__in=camping_lodgings,
                status=Reservation.Status.ACTIVE,
                end_date__gte=today,
            ).aggregate(total=Sum("people"))["total"]
            or 0
        )
        parque.disponibilidad_actual = max(total - used, 0)
    return render(request, "mapa/mapa.html", {"parques": parques})


@login_required
def perfil(request):
    show_past = request.GET.get("show") == "past"
    reservas = ReservationService.get_user_reservations(request.user)

    # Por default: actuales (ACTIVE + USED). Con ?show=past sólo PAST.
    if show_past:
        reservas = reservas.filter(status=Reservation.Status.PAST)
    else:
        reservas = reservas.exclude(status=Reservation.Status.PAST)

    q = (request.GET.get("q") or "").strip()
    date_from = (request.GET.get("from") or "").strip()
    date_to = (request.GET.get("to") or "").strip()
    sort = (request.GET.get("sort") or "recent").strip().lower()

    if q:
        reservas = reservas.filter(
            Q(park__name__icontains=q) | Q(lodging__name__icontains=q)
        )

    if date_from:
        try:
            reservas = reservas.filter(start_date__gte=date.fromisoformat(date_from))
        except ValueError:
            date_from = ""

    if date_to:
        try:
            reservas = reservas.filter(end_date__lte=date.fromisoformat(date_to))
        except ValueError:
            date_to = ""

    sort_map = {
        "recent": ("-start_date", "-created_at"),
        "oldest": ("start_date", "created_at"),
        "park": ("park__name", "start_date"),
    }
    reservas = reservas.order_by(*sort_map.get(sort, ("-start_date", "-created_at")))

    filters = {
        "q": q,
        "from": date_from,
        "to": date_to,
        "sort": sort,
    }
    return render(request, "user/perfil.html", {
        "reservas": reservas,
        "filters": filters,
        "show_past": show_past,
    })


@login_required
def reservation_list(request):
    return redirect("sistema_app:perfil")


@login_required
def reservation_create(request):
    park_id = request.GET.get("park")
    target = resolve_url("sistema_app:mapa")
    if park_id and park_id.isdigit():
        target = f"{target}?park={park_id}"
    return redirect(target)


@login_required
@require_POST
def crear_reserva(request):
    lodging_id = request.POST.get("lodging_id")
    fecha_inicio = request.POST.get("fecha_inicio")
    fecha_termino = request.POST.get("fecha_termino")
    num_personas = request.POST.get("num_personas")

    try:
        lodging = Lodging.objects.select_related("park").get(pk=int(lodging_id))
        start_date = date.fromisoformat(fecha_inicio)
        end_date = date.fromisoformat(fecha_termino)
        people = int(num_personas)
    except (TypeError, ValueError, Lodging.DoesNotExist):
        messages.error(request, "Datos de la reserva inválidos.")
        return redirect("sistema_app:mapa")

    try:
        reservation = ReservationService.create_reservation(
            user=request.user,
            lodging=lodging,
            start_date=start_date,
            end_date=end_date,
            n_people=people,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("sistema_app:mapa")

    messages.success(request, f"Reservación #{reservation.pk} confirmada.")
    return redirect("sistema_app:perfil")


@login_required
@require_POST
def reservation_cancel(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    try:
        ReservationService.cancel_reservation(request.user, reservation)
        messages.success(request, f"Reservación #{reservation.pk} cancelada.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("sistema_app:perfil")


def disponibilidad_api(request):
    """Devuelve los Lodgings disponibles para un parque, tipo y rango de fechas."""
    park_id = request.GET.get("park_id")
    kind = (request.GET.get("kind") or "").upper()
    start = request.GET.get("start_date")
    end = request.GET.get("end_date")

    if kind not in Lodging.Kind.values:
        return JsonResponse({"error": "kind inválido."}, status=400)

    try:
        park = Park.objects.active().get(pk=int(park_id))
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError, Park.DoesNotExist):
        return JsonResponse({"error": "parámetros inválidos."}, status=400)

    if end_date <= start_date:
        return JsonResponse({"lodgings": []})

    lodgings = AvailabilityService.available_lodgings(
        park, kind, start_date, end_date
    )
    return JsonResponse({
        "lodgings": [
            {
                "id": lo.id,
                "name": lo.name,
                "kind": lo.kind,
                "capacity": lo.capacity,
                "available": getattr(lo, "available_capacity", lo.capacity),
                "description": lo.description,
            }
            for lo in lodgings
        ]
    })
