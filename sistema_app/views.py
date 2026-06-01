"""Vistas HTTP del sitio: páginas para el usuario y endpoints en JSON."""

from datetime import date

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import CustomPasswordChangeForm, CustomUserCreationForm
from .models import Lodging, LoginAttempt, Park, PendingRegistration, PasswordResetToken, Reservation
from .services import (
    AvailabilityService,
    NotificationService,
    ReservationService,
    generate_verification_code,
    mask_email,
)
from .utils import generate_qr_png


def home(request):
    """Renderiza la portada con los parques destacados y su disponibilidad actual."""
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
    """Renderiza la página informativa del festival."""
    return render(request, "festival.html")


@require_GET
def reservation_qr_png(request, token):
    """
    Devuelve el QR de una reservación como PNG para clientes de correo.

    La URL usa el token opaco de check-in, no el ID numérico de la reserva,
    para que pueda abrirse desde Gmail/Outlook móvil sin iniciar sesión.
    """
    reservation = get_object_or_404(Reservation, checkin_token=token)
    checkin_path = reverse(
        "admin:sistema_app_reservation_checkin_data",
        args=[reservation.checkin_token],
    )
    checkin_url = f"{settings.SITE_URL.rstrip('/')}{checkin_path}"
    return HttpResponse(generate_qr_png(checkin_url), content_type="image/png")


def _safe_next(request, fallback="sistema_app:home"):
    """Devuelve una URL de redirección segura tomada de los parámetros de la solicitud."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return resolve_url(fallback)


PENDING_REGISTRATION_KEY = "pending_registration_id"


def _send_pending_code(pending: PendingRegistration) -> None:
    """Envía por correo el código de verificación al usuario en proceso de registro."""
    NotificationService.send_verification_email(
        recipient_email=pending.email,
        code=pending.code,
        recipient_name=pending.username,
    )


def register(request):
    """Procesa el formulario de registro y dispara el envío del código de verificación."""
    data = {"form": CustomUserCreationForm(), "next": request.GET.get("next", "")}
    if request.method == "POST":
        formulario = CustomUserCreationForm(data=request.POST)
        if formulario.is_valid():
            cleaned = formulario.cleaned_data
            # Solo se eliminan los registros pendientes ya expirados. Los
            # activos los rechaza el propio formulario, lo que permite a
            # un usuario reintentar después de cinco minutos.
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
    """Recupera el registro pendiente asociado a la sesión actual del usuario."""
    pending_id = request.session.get(PENDING_REGISTRATION_KEY)
    if not pending_id:
        return None
    pending = PendingRegistration.objects.filter(pk=pending_id).first()
    if not pending:
        request.session.pop(PENDING_REGISTRATION_KEY, None)
    return pending


def verify_email_page(request):
    """Muestra la pantalla donde el usuario ingresa el código que recibió por correo."""
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
    """
    Valida el código de verificación enviado por correo y crea la cuenta del usuario.

    Devuelve un JSON con el resultado. Cuando el código es correcto, la
    cuenta queda creada y el usuario inicia sesión automáticamente.
    """
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

    # Defensa contra carreras: alguien pudo haber tomado el nombre de
    # usuario o el correo entre el alta y la verificación.
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
        # La contraseña ya viene en formato hash desde el registro.
        user.password = pending.password
        user.save()
        pending.delete()

    auth_login(request, user)
    request.session.pop(PENDING_REGISTRATION_KEY, None)
    return JsonResponse({"ok": True})


@require_POST
def resend_verification_code_api(request):
    """Reenvía el código de verificación respetando el tiempo mínimo entre solicitudes."""
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
    """Procesa el inicio de sesión y aplica el bloqueo tras varios intentos fallidos."""
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
    """Cierra la sesión y devuelve al usuario a la portada."""
    logout(request)
    return redirect(to="sistema_app:home")


def mapa(request):
    """Renderiza el mapa con los parques activos y su disponibilidad actual."""
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
    """
    Muestra el perfil del usuario con sus reservas filtradas y ordenadas.

    Antes de listar, marca como pasadas las reservas activas cuya fecha
    de término ya quedó atrás. Las reservas canceladas no se muestran.
    El panel principal muestra solo las activas y la pestaña de pasadas
    muestra las usadas o vencidas.
    """
    today = timezone.localdate()
    Reservation.objects.filter(
        user=request.user,
        status=Reservation.Status.ACTIVE,
        end_date__lte=today,
    ).update(status=Reservation.Status.PAST)

    show_past = request.GET.get("show") == "past"
    reservas = ReservationService.get_user_reservations(request.user)

    reservas = reservas.exclude(status=Reservation.Status.CANCELLED)
    if show_past:
        reservas = reservas.filter(
            status__in=[Reservation.Status.PAST, Reservation.Status.USED]
        )
    else:
        reservas = reservas.filter(status=Reservation.Status.ACTIVE)

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
    """Redirige al perfil del usuario, que es el listado real de reservas."""
    return redirect("sistema_app:perfil")


@login_required
def reservation_create(request):
    """Redirige al mapa con el parque preseleccionado para iniciar una reserva."""
    park_id = request.GET.get("park")
    target = resolve_url("sistema_app:mapa")
    if park_id and park_id.isdigit():
        target = f"{target}?park={park_id}"
    return redirect(target)


@login_required
@require_POST
def crear_reserva(request):
    """Crea una reservación tomando los datos del formulario del mapa."""
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
    """Cancela una reservación del usuario; responde JSON para el flujo AJAX.

    Devuelve 200 {"ok": true} si se cancela, o 409 {"error": ...} si la
    reserva ya no es cancelable (p. ej. fue marcada como usada en otra
    pestaña). El front muestra el diálogo de error y recarga la página.
    """
    reservation = get_object_or_404(Reservation, pk=pk)
    try:
        ReservationService.cancel_reservation(request.user, reservation)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=409)
    return JsonResponse({"ok": True})


@login_required
def reservation_comprobante(request, pk):
    """Página imprimible con el QR y los datos de una reservación del usuario."""
    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
    return render(request, "user/comprobante.html", {"reserva": reservation})


def disponibilidad_api(request):
    """Devuelve los hospedajes disponibles para un parque, tipo y rango de fechas."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Recuperar contraseña (sin sesión activa)
# ─────────────────────────────────────────────────────────────────────────────

PASSWORD_RESET_SESSION_KEY = "password_reset_token_id"


def password_reset_request(request):
    """Muestra el formulario de solicitud de restablecimiento de contraseña."""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return render(request, "registration/resetRequest.html", {
                "error": "Este correo no está asociado a ninguna cuenta.",
                "email": email,
            })
        if user:
            # Invalidar tokens anteriores no usados
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
            token = PasswordResetToken.objects.create(
                user=user,
                code=generate_verification_code() + str(__import__("secrets").randbelow(10)),
            )
            from .services import NotificationService
            NotificationService.send_password_reset_email(
                recipient_email=user.email,
                code=token.code,
                recipient_name=user.first_name or user.username,
            )
            request.session[PASSWORD_RESET_SESSION_KEY] = token.pk
        # Siempre redirigir para no revelar si el correo existe
        return redirect("sistema_app:password_reset_verify")
    return render(request, "registration/resetRequest.html")


def password_reset_verify(request):
    """Muestra la pantalla de ingreso del código recibido por correo."""
    token_id = request.session.get(PASSWORD_RESET_SESSION_KEY)
    if not token_id:
        return redirect("sistema_app:password_reset_request")
    token = PasswordResetToken.objects.filter(pk=token_id, is_used=False).first()
    if not token:
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        return redirect("sistema_app:password_reset_request")
    from .utils import mask_email
    return render(request, "registration/resetVerify.html", {
        "masked_email": mask_email(token.user.email),
        "resend_in": token.seconds_until_resend(),
    })


@require_POST
def password_reset_verify_api(request):
    """Valida el código ingresado y marca el token como verificado."""
    token_id = request.session.get(PASSWORD_RESET_SESSION_KEY)
    if not token_id:
        return JsonResponse({"ok": False, "error": "Sesión expirada."}, status=400)

    token = PasswordResetToken.objects.filter(pk=token_id, is_used=False).first()
    if not token:
        return JsonResponse({"ok": False, "error": "Token inválido."}, status=400)

    if token.is_expired():
        return JsonResponse({"ok": False, "error": "El código ha expirado."}, status=400)

    import json
    try:
        body = json.loads(request.body)
        code = (body.get("code") or "").strip()
    except Exception:
        code = ""

    if code != token.code:
        return JsonResponse({"ok": False, "error": "Código incorrecto."}, status=400)

    token.is_verified = True
    token.save(update_fields=["is_verified"])
    return JsonResponse({"ok": True})


@require_POST
def password_reset_resend_api(request):
    """Reenvía el código de restablecimiento al correo del usuario."""
    token_id = request.session.get(PASSWORD_RESET_SESSION_KEY)
    if not token_id:
        return JsonResponse({"ok": False, "error": "Sesión expirada."}, status=400)

    token = PasswordResetToken.objects.filter(pk=token_id, is_used=False).first()
    if not token:
        return JsonResponse({"ok": False, "error": "Token inválido."}, status=400)

    if token.seconds_until_resend() > 0:
        return JsonResponse({"ok": False, "error": "Espera antes de reenviar."}, status=429)

    from .utils import generate_verification_code
    import secrets as _secrets
    token.code = generate_verification_code() + str(_secrets.randbelow(10))
    token.created_at = timezone.now()
    token.is_verified = False
    token.save(update_fields=["code", "created_at", "is_verified"])

    from .services import NotificationService
    NotificationService.send_password_reset_email(
        recipient_email=token.user.email,
        code=token.code,
        recipient_name=token.user.first_name or token.user.username,
    )
    return JsonResponse({"ok": True, "resend_in": PasswordResetToken.RESEND_COOLDOWN_SECONDS})


def password_reset_confirm(request):
    """Muestra el formulario de nueva contraseña (solo si el código fue verificado)."""
    token_id = request.session.get(PASSWORD_RESET_SESSION_KEY)
    if not token_id:
        return redirect("sistema_app:password_reset_request")

    # Carga el token junto con el usuario en una sola consulta
    token = PasswordResetToken.objects.select_related('user').filter(
        pk=token_id, is_used=False, is_verified=True
    ).first()

    if not token or token.is_expired():
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        return redirect("sistema_app:password_reset_request")

    if request.method == "POST":
        form = SetPasswordForm(user=token.user, data=request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()  # set_password + save sobre token.user

                token.is_used = True
                token.save(update_fields=["is_used"])

                # Invalidar otros tokens pendientes del mismo usuario
                PasswordResetToken.objects.filter(
                    user=token.user, is_used=False
                ).update(is_used=True)

            # Limpiar sesión y redirigir
            request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
            return redirect("sistema_app:password_reset_done")
    else:
        form = SetPasswordForm(user=token.user)

    return render(request, "registration/resetConfirm.html", {"form": form})


def password_reset_done(request):
    """Pantalla de confirmación tras cambiar la contraseña exitosamente."""
    return render(request, "registration/resetDone.html")


# ─────────────────────────────────────────────────────────────────────────────
# Cambiar contraseña (con sesión activa, desde el perfil)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def password_change(request):
    """Permite al usuario autenticado cambiar su contraseña desde el perfil."""
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            # Mantiene la sesión activa tras el cambio de contraseña.
            update_session_auth_hash(request, form.user)
            messages.success(request, "Tu contraseña se actualizó correctamente.")
            return redirect("sistema_app:perfil")
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, "registration/passwordChange.html", {"form": form})
