from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CustomUserCreationForm, ReservationForm
from .models import Park, Reservation
from .services import ReservationService


def home(request):
    return render(request, "home.html")


def _safe_next(request, fallback="sistema_app:home"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return resolve_url(fallback)


def register(request):
    data = {"form": CustomUserCreationForm(), "next": request.GET.get("next", "")}
    if request.method == "POST":
        formulario = CustomUserCreationForm(data=request.POST)
        if formulario.is_valid():
            formulario.save()
            user = authenticate(
                username=formulario.cleaned_data["username"],
                password=formulario.cleaned_data["password1"],
            )
            auth_login(request, user)
            return redirect(_safe_next(request))
        data["form"] = formulario
    return render(request, "registro/signIn.html", data)


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
    return render(request, "registro/logIn.html", data)


def logout_view(request):
    logout(request)
    return redirect(to="sistema_app:home")


def mapa(request):
    parques = Park.objects.active().prefetch_related("services")
    return render(request, "mapa/mapa.html", {"parques": parques})


@login_required
def reservation_create(request):
    if request.method == "POST":
        form = ReservationForm(request.POST)
        if form.is_valid():
            try:
                reservation = ReservationService.create_reservation(
                    user=request.user,
                    park=form.cleaned_data["park"],
                    visit_type=form.cleaned_data["visit_type"],
                    start_date=form.cleaned_data["start_date"],
                    end_date=form.cleaned_data["end_date"],
                    n_people=form.cleaned_data["people"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    f"Reservación #{reservation.pk} confirmada.",
                )
                return redirect("sistema_app:reservation_list")
    else:
        initial = {}
        park_id = request.GET.get("park")
        if park_id and park_id.isdigit():
            initial["park"] = int(park_id)
        form = ReservationForm(initial=initial)
    return render(request, "reservaciones/reservacion_form.html", {"form": form})


@login_required
def reservation_list(request):
    reservas = ReservationService.get_user_reservations(request.user)
    return render(
        request,
        "reservaciones/reservacion_list.html",
        {"reservaciones": reservas},
    )


@login_required
@require_POST
def reservation_cancel(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    try:
        ReservationService.cancel_reservation(request.user, reservation)
        messages.success(request, f"Reservación #{reservation.pk} cancelada.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("sistema_app:reservation_list")
