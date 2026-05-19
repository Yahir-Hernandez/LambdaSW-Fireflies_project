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

from .forms import CustomUserCreationForm
from .models import EmailVerification, Lodging, Park, Reservation
from .services import (
    AvailabilityService,
    NotificationService,
    ReservationService,
    generate_verification_code,
    mask_email,
)


def home(request):
    return render(request, "home.html")


def _safe_next(request, fallback="sistema_app:home"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return resolve_url(fallback)


PENDING_VERIFICATION_KEY = "pending_verification_user_id"


def _start_email_verification(user) -> EmailVerification:
    """Crea/reemplaza el código de verificación y dispara el correo."""
    EmailVerification.objects.filter(user=user).delete()
    code = generate_verification_code()
    verification = EmailVerification.objects.create(user=user, code=code)
    NotificationService.send_verification_email(user, code)
    return verification


def register(request):
    data = {"form": CustomUserCreationForm(), "next": request.GET.get("next", "")}
    if request.method == "POST":
        formulario = CustomUserCreationForm(data=request.POST)
        if formulario.is_valid():
            user = formulario.save(commit=False)
            user.is_active = False  # se activa al verificar el correo
            user.save()
            _start_email_verification(user)
            request.session[PENDING_VERIFICATION_KEY] = user.pk
            request.session["pending_verification_next"] = request.POST.get("next", "")
            return redirect("sistema_app:verify_email")
        data["form"] = formulario
    return render(request, "registration/sign_up.html", data)


def verify_email_page(request):
    user_id = request.session.get(PENDING_VERIFICATION_KEY)
    if not user_id:
        return redirect("sistema_app:register")
    user = User.objects.filter(pk=user_id, is_active=False).first()
    if not user:
        request.session.pop(PENDING_VERIFICATION_KEY, None)
        return redirect("sistema_app:register")

    verification = EmailVerification.objects.filter(user=user).first()
    resend_in = verification.seconds_until_resend() if verification else 0
    return render(
        request,
        "registration/verify_email.html",
        {
            "masked_email": mask_email(user.email),
            "resend_in": resend_in,
        },
    )


@require_POST
def verify_email_api(request):
    user_id = request.session.get(PENDING_VERIFICATION_KEY)
    if not user_id:
        return JsonResponse({"error": "Tu sesión de verificación expiró. Regístrate nuevamente."}, status=400)
    user = User.objects.filter(pk=user_id, is_active=False).first()
    if not user:
        request.session.pop(PENDING_VERIFICATION_KEY, None)
        return JsonResponse({"error": "Usuario no encontrado."}, status=400)

    code = (request.POST.get("code") or "").strip()
    if not code:
        return JsonResponse({"error": "Ingresa el código que recibiste por correo."}, status=400)

    verification = EmailVerification.objects.filter(user=user).first()
    if not verification:
        return JsonResponse({"error": "Solicita un código primero."}, status=400)
    if verification.is_expired():
        verification.delete()
        return JsonResponse({"error": "El código expiró. Solicita uno nuevo."}, status=400)
    if verification.code != code:
        return JsonResponse({"error": "Código incorrecto."}, status=400)

    user.is_active = True
    user.save(update_fields=["is_active"])
    verification.delete()
    auth_login(request, user)
    request.session.pop(PENDING_VERIFICATION_KEY, None)
    request.session.pop("pending_verification_next", None)
    return JsonResponse({"ok": True})


@require_POST
def resend_verification_code_api(request):
    user_id = request.session.get(PENDING_VERIFICATION_KEY)
    if not user_id:
        return JsonResponse({"error": "Tu sesión de verificación expiró. Regístrate nuevamente."}, status=400)
    user = User.objects.filter(pk=user_id, is_active=False).first()
    if not user:
        request.session.pop(PENDING_VERIFICATION_KEY, None)
        return JsonResponse({"error": "Usuario no encontrado."}, status=400)

    existing = EmailVerification.objects.filter(user=user).first()
    if existing:
        remaining = existing.seconds_until_resend()
        if remaining > 0:
            return JsonResponse(
                {"error": f"Espera {remaining} segundos para reenviar.", "retry_in": remaining},
                status=429,
            )

    _start_email_verification(user)
    return JsonResponse({"ok": True, "masked_email": mask_email(user.email)})


def login(request):
    data = {"form": AuthenticationForm(), "next": request.GET.get("next", "")}
    if request.method == "POST":
        formulario = AuthenticationForm(data=request.POST)
        if formulario.is_valid():
            username = formulario.cleaned_data["username"]
            password = formulario.cleaned_data["password"]
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect(_safe_next(request))
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
    reservas = ReservationService.get_user_reservations(request.user)
    return render(request, "user/perfil.html", {"reservas": reservas})


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
