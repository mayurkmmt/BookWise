import datetime
import json
import random

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    IntegerField,
    Max,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.accounts.models import OTPVerification, User
from apps.bookings.forms import BookingForm
from apps.bookings.models import Appointment, AppointmentService
from apps.bookings.services import BookingService, BookingVerificationError
from apps.bookings.utils import send_booking_email
from apps.common.mixins import (
    CustomerRequiredMixin,
    ProviderDataIsolationMixin,
    ProviderRequiredMixin,
)
from apps.services.models import Service, ServiceProvider, WorkingHours


class ServiceAvailableTimesView(View):
    def get(self, request, provider_id):
        date_str = request.GET.get("date")
        duration_str = request.GET.get("duration")

        if not date_str or not duration_str:
            return JsonResponse(
                {"error": "Date and total duration are required"}, status=400
            )

        try:
            target_date = (
                datetime.datetime.strptime(date_str, "%Y-%m-%d")
                .replace(tzinfo=datetime.timezone.utc)
                .date()
            )
            total_duration = int(duration_str)
        except ValueError:
            return JsonResponse({"error": "Invalid parameters"}, status=400)

        try:
            provider = ServiceProvider.objects.get(
                id=provider_id, is_active=True, is_delete=False
            )
        except ServiceProvider.DoesNotExist:
            return JsonResponse({"error": "Provider unavailable"}, status=404)

        now = timezone.localtime().replace(tzinfo=None)
        if target_date < now.date():
            return JsonResponse({"slots": []})

        if target_date == now.date():
            min_allowed_time = now + datetime.timedelta(hours=1)
        else:
            min_allowed_time = None

        day_of_week = target_date.weekday()

        try:
            hours = WorkingHours.objects.get(provider=provider, day_of_week=day_of_week)
        except WorkingHours.DoesNotExist:
            return JsonResponse({"slots": []})

        if not hours.is_working_day:
            return JsonResponse({"slots": []})

        slots = []
        current_time = datetime.datetime.combine(target_date, hours.start_time)
        end_time = datetime.datetime.combine(target_date, hours.end_time)

        appointments = Appointment.objects.filter(
            provider=provider, date=target_date, is_delete=False
        ).exclude(status__in=["cancelled", "rescheduled"])

        while current_time + datetime.timedelta(minutes=total_duration) <= end_time:
            slot_start = current_time
            slot_end = current_time + datetime.timedelta(minutes=total_duration)

            is_available = True

            if min_allowed_time and slot_start < min_allowed_time:
                is_available = False

            if is_available:
                for appt in appointments:
                    appt_start = datetime.datetime.combine(target_date, appt.start_time)
                    appt_end = datetime.datetime.combine(target_date, appt.end_time)
                    if max(slot_start, appt_start) < min(slot_end, appt_end):
                        is_available = False
                        break

            if is_available:
                slots.append(slot_start.strftime("%H:%M"))

            current_time += datetime.timedelta(minutes=15)

        return JsonResponse({"slots": slots})


class CustomerBookingEngineView(FormView):
    template_name = "bookings/booking_wizard.html"
    form_class = BookingForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, "role", "") in [
            "provider",
            "admin",
        ]:
            messages.error(
                request,
                "Only customers and guest users can book appointments. Please log out or use a customer account to continue.",
            )
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["is_reschedule"] = False
        return kwargs

    def get_services(self):
        service_ids = self.request.GET.getlist("service")
        if not service_ids:
            return Service.objects.none()
        return Service.objects.filter(
            id__in=service_ids,
            provider_id=self.kwargs["provider_id"],
            is_active=True,
            is_delete=False,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = self.get_services()
        context["services"] = services
        context["provider"] = get_object_or_404(
            ServiceProvider,
            pk=self.kwargs["provider_id"],
            is_active=True,
            is_delete=False,
        )
        context["total_duration"] = sum(s.duration for s in services)
        context["total_price"] = sum(s.price for s in services)
        return context

    def form_valid(self, form):
        provider_id = self.kwargs["provider_id"]
        services = self.get_services()

        start_time = form.cleaned_data["start_time"]
        date = form.cleaned_data["date"]

        user_instance = (
            getattr(self.request, "user", None)
            if self.request.user.is_authenticated
            else None
        )

        try:
            if user_instance:
                appointment = BookingService.process_authenticated_booking(
                    user_instance, provider_id, services, date, start_time, self.request
                )
                return redirect(
                    "booking_success", booking_reference=appointment.booking_reference
                )
            else:
                guest_name = form.cleaned_data.get("guest_name")
                guest_email = form.cleaned_data.get("guest_email")
                guest_phone_number = form.cleaned_data.get("guest_phone_number")

                BookingService.process_guest_booking_intent(
                    provider_id,
                    services,
                    date,
                    start_time,
                    guest_name,
                    guest_email,
                    guest_phone_number,
                    self.request,
                )
                return redirect("guest_otp_verify")
        except BookingVerificationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)


class BookingSuccessView(DetailView):
    model = Appointment
    template_name = "bookings/booking_success.html"
    context_object_name = "appointment"
    slug_url_kwarg = "booking_reference"
    slug_field = "booking_reference"


class GuestBookingOTPVerifyView(View):
    template_name = "bookings/guest_otp_verify.html"

    def get(self, request, *args, **kwargs):
        if "guest_booking_email" not in request.session:
            messages.error(request, "No pending booking found.")
            return redirect("home")
        return render(
            request,
            self.template_name,
            {"email": request.session.get("guest_booking_email")},
        )

    def post(self, request, *args, **kwargs):
        if "guest_booking_email" not in request.session:
            messages.error(request, "No pending booking found.")
            return redirect("home")

        guest_email = request.session["guest_booking_email"]

        if request.POST.get("action") == "resend":
            otp = str(random.randint(100000, 999999))
            OTPVerification.objects.filter(email=guest_email).update(otp=otp)

            html_content = render_to_string(
                "emails/otp_notification.html",
                {
                    "otp": otp,
                    "preheader_message": "Verify your email to finalize your secure booking.",
                },
            )
            text_content = strip_tags(html_content)

            msg = EmailMultiAlternatives(
                "BookWise: Verify Your Secure Booking (New Code)",
                text_content,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bookwisetest.com"),
                [guest_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)

            messages.success(
                request, "A new verification code has been sent to your email."
            )
            return redirect("guest_otp_verify")

        submitted_otp = request.POST.get("otp", "").strip()

        try:
            otp_record = OTPVerification.objects.get(
                email=guest_email, otp=submitted_otp
            )
        except OTPVerification.DoesNotExist:
            return render(
                request,
                self.template_name,
                {
                    "error": "Invalid 6-digit code. Please try again.",
                    "email": guest_email,
                },
            )

        booking_data = json.loads(otp_record.registration_data)

        guest_email = booking_data["guest_email"]
        matched_user = User.objects.filter(email=guest_email).first()

        provider = ServiceProvider.objects.get(id=booking_data["provider_id"])

        date = datetime.date.fromisoformat(booking_data["date"])
        start_time = datetime.time.fromisoformat(booking_data["start_time"])
        end_time = datetime.time.fromisoformat(booking_data["end_time"])

        appointment = Appointment(
            provider=provider,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status="pending",
        )

        if matched_user:
            appointment.customer_user = matched_user
            appointment.created_by = matched_user
            appointment.modified_by = matched_user
        else:
            appointment.guest_name = booking_data["guest_name"]
            appointment.guest_email = guest_email
            appointment.guest_phone_number = booking_data["guest_phone_number"]

        appointment.save()

        services = Service.objects.filter(id__in=booking_data["service_ids"])
        for s in services:
            AppointmentService.objects.create(
                appointment=appointment,
                service=s,
                service_price=s.price,
                service_duration=s.duration,
                created_by=matched_user if matched_user else None,
                modified_by=matched_user if matched_user else None,
            )

        send_booking_email(appointment, "booked", request)

        otp_record.delete()
        del request.session["guest_booking_email"]

        return redirect(
            "booking_success", booking_reference=appointment.booking_reference
        )


class ProviderAppointmentListView(
    ProviderRequiredMixin, ProviderDataIsolationMixin, ListView
):
    model = Appointment
    template_name = "provider/appointment_list.html"
    context_object_name = "appointments"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()

        status = self.request.GET.get("status")
        search = self.request.GET.get("search")
        date_range = self.request.GET.get("date_range")
        service_id = self.request.GET.get("service")

        if date_range:
            parts = date_range.split(" to ")
            if len(parts) == 2:
                qs = qs.filter(date__gte=parts[0], date__lte=parts[1])
            elif len(parts) == 1 and parts[0]:
                qs = qs.filter(date=parts[0])
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)

        if service_id:
            services = [s.strip() for s in service_id.split(",") if s.strip()]
            if services:
                qs = qs.filter(appointment_services__service_id__in=services)

        if search:
            q_objects = (
                Q(appointment_services__service__title__icontains=search)
                | Q(customer_user__email__icontains=search)
                | Q(customer_user__phone_number__icontains=search)
                | Q(guest_name__icontains=search)
                | Q(guest_email__icontains=search)
                | Q(guest_phone_number__icontains=search)
                | Q(status__icontains=search)
                | Q(booking_reference__icontains=search)
            )

            qs = qs.filter(q_objects)

        now = timezone.localtime()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        current_time = now.time()

        qs = qs.distinct().annotate(
            order_group=Case(
                When(status="cancelled", then=Value(6)),
                When(
                    date=today,
                    start_time__gte=current_time,
                    status__in=["pending", "confirmed"],
                    then=Value(1),
                ),
                When(date=tomorrow, status__in=["pending", "confirmed"], then=Value(2)),
                When(
                    date__gt=tomorrow,
                    status__in=["pending", "confirmed"],
                    then=Value(3),
                ),
                When(date=today, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        return qs.order_by("order_group", "date", "start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        context["filter_query_string"] = (
            f"&{query_params.urlencode()}" if query_params else ""
        )
        context["provider_services"] = (
            self.request.user.service_provider.services.filter(
                is_active=True, is_delete=False
            )
        )

        status = self.request.GET.get("status", "")
        service_id = self.request.GET.get("service", "")
        context["selected_statuses"] = [
            s.strip() for s in status.split(",") if s.strip()
        ]
        context["selected_services"] = [
            s.strip() for s in service_id.split(",") if s.strip()
        ]
        return context


class ProviderAppointmentDetailView(
    ProviderRequiredMixin, ProviderDataIsolationMixin, DetailView
):
    model = Appointment
    template_name = "provider/appointment_detail.html"
    context_object_name = "appointment"

    def get_queryset(self):
        return Appointment.objects.filter(
            provider=self.request.user.service_provider, is_delete=False
        ).prefetch_related("appointment_services__service")


class UpdateAppointmentStatusView(ProviderRequiredMixin, View):
    def post(self, request, pk):
        try:
            data = json.loads(request.body)
            new_status = data.get("status")
        except (json.JSONDecodeError, ValueError, TypeError):
            return JsonResponse(
                {"status": "error", "message": "Invalid data"}, status=400
            )

        try:
            appointment = Appointment.objects.get(
                pk=pk, provider=request.user.service_provider, is_delete=False
            )
        except Appointment.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Appointment not found"}, status=404
            )

        if new_status in dict(Appointment.STATUS_CHOICES):
            appointment.status = new_status
            appointment.modified_by = request.user
            appointment.save(update_fields=["status", "modified_by"])

            # Fire automated transactional email seamlessly indicating new confirmed/cancelled provider overrides
            send_booking_email(appointment, new_status, request)

            return JsonResponse({"status": "success", "new_status": new_status})
        return JsonResponse({"status": "error", "message": "Invalid status"})


class CustomerAppointmentListView(CustomerRequiredMixin, ListView):
    model = Appointment
    template_name = "bookings/my_appointments.html"
    context_object_name = "appointments"
    paginate_by = 5

    def get_queryset(self):
        qs = Appointment.objects.filter(
            customer_user=self.request.user, is_delete=False
        )

        status = self.request.GET.get("status")
        search = self.request.GET.get("search")
        date_range = self.request.GET.get("date_range")
        service_id = self.request.GET.get("service")

        if date_range:
            parts = date_range.split(" to ")
            if len(parts) == 2:
                qs = qs.filter(date__gte=parts[0], date__lte=parts[1])
            elif len(parts) == 1 and parts[0]:
                qs = qs.filter(date=parts[0])

        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)

        if service_id:
            services = [s.strip() for s in service_id.split(",") if s.strip()]
            if services:
                qs = qs.filter(appointment_services__service_id__in=services)

        if search:
            q_objects = (
                Q(appointment_services__service__title__icontains=search)
                | Q(provider__business_name__icontains=search)
                | Q(provider__user__email__icontains=search)
                | Q(provider__user__phone_number__icontains=search)
                | Q(status__icontains=search)
                | Q(booking_reference=search)
            )

            qs = qs.filter(q_objects)

        # return qs.distinct().order_by('-date', '-start_time')
        return qs.distinct().order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        context["filter_query_string"] = (
            f"&{query_params.urlencode()}" if query_params else ""
        )

        context["available_services"] = Service.objects.filter(
            appointment_services__appointment__customer_user=self.request.user,
            appointment_services__appointment__is_delete=False,
        ).distinct()

        status = self.request.GET.get("status", "")
        service_id = self.request.GET.get("service", "")
        context["selected_statuses"] = [
            s.strip() for s in status.split(",") if s.strip()
        ]
        context["selected_services"] = [
            s.strip() for s in service_id.split(",") if s.strip()
        ]
        return context


class CustomerAppointmentDetailView(CustomerRequiredMixin, DetailView):
    model = Appointment
    template_name = "bookings/appointment_detail.html"
    context_object_name = "appointment"

    def get_queryset(self):
        return Appointment.objects.filter(
            customer_user=self.request.user, is_delete=False
        ).prefetch_related("appointment_services__service")


class CustomerCancelAppointmentView(CustomerRequiredMixin, View):
    def post(self, request, pk):
        try:
            appointment = Appointment.objects.get(
                pk=pk, customer_user=request.user, is_delete=False
            )
        except Appointment.DoesNotExist:
            messages.error(request, "Appointment lookup failed.")
            return redirect("customer_appointments")

        now = timezone.now()
        dt_start = datetime.datetime.combine(appointment.date, appointment.start_time)
        dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())

        if dt_start < (now + datetime.timedelta(hours=24)):
            messages.error(
                request,
                "Appointments cannot be cancelled within 24 hours of the scheduled time. Please contact the provider directly.",
            )
            return redirect("customer_appointments")

        if appointment.status == "confirmed":
            messages.error(
                request,
                "Confirmed appointments cannot be cancelled. Please contact the provider directly.",
            )
            return redirect("customer_appointments")

        if appointment.status in ["cancelled", "completed"]:
            messages.error(
                request, "Cannot alter historical or previously cancelled bookings."
            )
            return redirect("customer_appointments")

        appointment.status = "cancelled"
        appointment.modified_by = request.user
        appointment.save(update_fields=["status", "modified_by"])

        send_booking_email(appointment, "cancelled", request)

        messages.success(request, "Booking successfully retracted and cancelled.")
        return redirect("customer_appointments")


class CustomerRescheduleEngineView(CustomerRequiredMixin, FormView):
    template_name = "bookings/booking_wizard.html"
    form_class = BookingForm

    def get_appointment(self):
        return get_object_or_404(
            Appointment,
            pk=self.kwargs["pk"],
            customer_user=self.request.user,
            is_delete=False,
        )

    def dispatch(self, request, *args, **kwargs):
        try:
            appointment = self.get_appointment()
            now = timezone.now()
            dt_start = datetime.datetime.combine(
                appointment.date, appointment.start_time
            )
            dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())

            if dt_start < (now + datetime.timedelta(hours=24)):
                messages.error(
                    request,
                    "Appointments cannot be rescheduled within 24 hours of the scheduled time. Please contact the provider directly.",
                )
                return redirect("customer_appointments")

            if appointment.status == "confirmed":
                messages.error(
                    request,
                    "Confirmed appointments cannot be rescheduled. Please contact the provider directly.",
                )
                return redirect("customer_appointments")
        except Exception:  # noqa: BLE001, S110
            pass
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.get_appointment()

        # Inject standard wizard layouts dynamically without triggering DB calls
        services = [pt.service for pt in appointment.appointment_services.all()]
        context["services"] = services
        context["provider"] = appointment.provider
        context["total_duration"] = sum(
            s.service_duration for s in appointment.appointment_services.all()
        )
        context["total_price"] = appointment.total_price
        context["rescheduling"] = True
        return context

    def form_valid(self, form):
        appointment = self.get_appointment()
        start_time = form.cleaned_data["start_time"]
        date = form.cleaned_data["date"]

        try:
            appointment = BookingService.reschedule_appointment(
                appointment, date, start_time, self.request.user, self.request
            )
            return redirect(
                "booking_success", booking_reference=appointment.booking_reference
            )
        except BookingVerificationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)


class ProviderCustomerListView(
    ProviderRequiredMixin, ProviderDataIsolationMixin, ListView
):
    template_name = "provider/customer_list.html"
    context_object_name = "customers"
    paginate_by = 10

    def get_queryset(self):

        search = self.request.GET.get("search", "").lower()

        qs = (
            Appointment.objects.filter(
                provider=self.request.user.service_provider, is_delete=False
            )
            .annotate(
                resolved_email=Coalesce("customer_user__email", "guest_email"),
                resolved_name=Coalesce("customer_user__email", "guest_name"),
                resolved_phone=Cast(
                    Coalesce("customer_user__phone_number", "guest_phone_number"),
                    output_field=CharField(),
                ),
                is_registered=Case(
                    When(customer_user__isnull=False, then=Value("Registered")),
                    default=Value("Guest"),
                    output_field=CharField(),
                ),
            )
            .values(
                "resolved_email", "resolved_name", "resolved_phone", "is_registered"
            )
            .annotate(
                total_appointments=Count("id", distinct=True),
                total_spent=Sum("appointment_services__service_price"),
                last_appointment=Max("date"),
            )
            .exclude(resolved_email__isnull=True)
            .exclude(resolved_email="")
        )

        if search:
            qs = qs.filter(
                Q(resolved_email__icontains=search)
                | Q(resolved_name__icontains=search)
                | Q(resolved_phone__icontains=search)
            )

        customer_list = []
        for item in qs.order_by("-last_appointment"):
            customer_list.append(
                {
                    "email": item["resolved_email"],
                    "name": item["resolved_name"],
                    "phone": item["resolved_phone"] or "",
                    "total_appointments": item["total_appointments"],
                    "total_spent": item["total_spent"] or 0,
                    "last_appointment": item["last_appointment"],
                    "type": item["is_registered"],
                }
            )

        return customer_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        context["filter_query_string"] = (
            f"&{query_params.urlencode()}" if query_params else ""
        )
        return context


class ProviderCustomerDetailView(
    ProviderRequiredMixin, ProviderDataIsolationMixin, ListView
):
    template_name = "provider/customer_detail.html"
    context_object_name = "appointments"
    paginate_by = 10

    def get_queryset(self):
        email = self.kwargs.get("email")

        now = timezone.localtime()
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        current_time = now.time()

        qs = Appointment.objects.filter(
            Q(customer_user__email=email) | Q(guest_email=email),
            provider=self.request.user.service_provider,
            is_delete=False,
        )

        return qs.annotate(
            order_group=Case(
                When(status="cancelled", then=Value(6)),
                When(
                    date=today,
                    start_time__gte=current_time,
                    status__in=["pending", "confirmed"],
                    then=Value(1),
                ),
                When(date=tomorrow, status__in=["pending", "confirmed"], then=Value(2)),
                When(
                    date__gt=tomorrow,
                    status__in=["pending", "confirmed"],
                    then=Value(3),
                ),
                When(date=today, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        ).order_by("order_group", "date", "start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        email = self.kwargs.get("email")
        context["customer_email"] = email
        first_appt = self.get_queryset().first()
        if first_appt:
            context["customer_name"] = (
                first_appt.customer_user.email
                if first_appt.customer_user
                else first_appt.guest_name
            )
            context["customer_phone"] = (
                getattr(first_appt.customer_user, "phone_number", "")
                if first_appt.customer_user
                else first_appt.guest_phone_number
            )
            context["customer_type"] = (
                "Registered" if first_appt.customer_user else "Guest"
            )

        all_appts = self.get_queryset()
        context["total_appointments"] = all_appts.count()
        context["pending_appointments"] = all_appts.filter(status="pending").count()
        context["confirmed_appointments"] = all_appts.filter(status="confirmed").count()
        context["cancelled_appointments"] = all_appts.filter(status="cancelled").count()
        context["total_spent"] = sum(a.total_price for a in all_appts)
        return context


class GuestManageBookingView(DetailView):
    model = Appointment
    template_name = "bookings/guest_manage.html"
    context_object_name = "appointment"
    slug_url_kwarg = "booking_reference"
    slug_field = "booking_reference"

    def get_queryset(self):
        return Appointment.objects.filter(
            customer_user__isnull=True, is_delete=False
        ).prefetch_related("appointment_services__service")


class GuestCancelAppointmentView(View):
    def post(self, request, booking_reference):
        try:
            appointment = Appointment.objects.get(
                booking_reference=booking_reference,
                customer_user__isnull=True,
                is_delete=False,
            )
        except Appointment.DoesNotExist:
            messages.error(request, "Appointment lookup failed.")
            return redirect("home")

        now = timezone.now()
        dt_start = datetime.datetime.combine(appointment.date, appointment.start_time)
        dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())

        if dt_start < (now + datetime.timedelta(hours=24)):
            messages.error(
                request,
                "Appointments cannot be cancelled within 24 hours of the scheduled time. Please contact the provider directly.",
            )
            return redirect(
                "guest_manage_appointment",
                booking_reference=appointment.booking_reference,
            )

        if appointment.status == "confirmed":
            messages.error(
                request,
                "Confirmed appointments cannot be cancelled. Please contact the provider directly.",
            )
            return redirect(
                "guest_manage_appointment",
                booking_reference=appointment.booking_reference,
            )

        if appointment.status in ["cancelled", "completed"]:
            messages.error(
                request, "Cannot alter historical or previously cancelled bookings."
            )
            return redirect(
                "guest_manage_appointment",
                booking_reference=appointment.booking_reference,
            )

        appointment.status = "cancelled"
        appointment.save(update_fields=["status"])

        send_booking_email(appointment, "cancelled", request)

        messages.success(request, "Booking successfully retracted and cancelled.")
        return redirect(
            "guest_manage_appointment", booking_reference=appointment.booking_reference
        )


class GuestRescheduleEngineView(FormView):
    template_name = "bookings/booking_wizard.html"
    form_class = BookingForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["is_reschedule"] = True
        return kwargs

    def get_appointment(self):
        return get_object_or_404(
            Appointment,
            booking_reference=self.kwargs["booking_reference"],
            customer_user__isnull=True,
            is_delete=False,
        )

    def get_initial(self):
        initial = super().get_initial()
        appointment = self.get_appointment()
        initial["guest_name"] = appointment.guest_name
        initial["guest_email"] = appointment.guest_email
        initial["guest_phone_number"] = appointment.guest_phone_number
        return initial

    def dispatch(self, request, *args, **kwargs):
        try:
            appointment = self.get_appointment()
            now = timezone.now()
            dt_start = datetime.datetime.combine(
                appointment.date, appointment.start_time
            )
            dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())

            if dt_start < (now + datetime.timedelta(hours=24)):
                messages.error(
                    request,
                    "Appointments cannot be rescheduled within 24 hours of the scheduled time. Please contact the provider directly.",
                )
                return redirect(
                    "guest_manage_appointment",
                    booking_reference=appointment.booking_reference,
                )

            if appointment.status == "confirmed":
                messages.error(
                    request,
                    "Confirmed appointments cannot be rescheduled. Please contact the provider directly.",
                )
                return redirect(
                    "guest_manage_appointment",
                    booking_reference=appointment.booking_reference,
                )
        except Exception:  # noqa: BLE001, S110
            pass
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.get_appointment()

        services = [pt.service for pt in appointment.appointment_services.all()]
        context["services"] = services
        context["provider"] = appointment.provider
        context["total_duration"] = sum(
            s.service_duration for s in appointment.appointment_services.all()
        )
        context["total_price"] = appointment.total_price
        context["rescheduling"] = True
        context["guest_rescheduling"] = True
        context["appointment"] = appointment
        return context

    def form_valid(self, form):

        with transaction.atomic():
            appointment = self.get_appointment()
            provider = ServiceProvider.objects.select_for_update().get(
                pk=appointment.provider.pk
            )

            start_time = form.cleaned_data["start_time"]
            date = form.cleaned_data["date"]

            now = timezone.now()

            dt_start = datetime.datetime.combine(date, start_time)
            dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())
            if dt_start < (now + datetime.timedelta(minutes=59)):
                messages.error(
                    self.request,
                    "Appointments must be booked at least 1 hour in advance.",
                )
                return self.form_invalid(form)

            if dt_start > (now + datetime.timedelta(days=90)):
                messages.error(
                    self.request,
                    "Appointments cannot be rescheduled more than 90 days in advance.",
                )
                return self.form_invalid(form)

            total_duration = sum(
                s.service_duration for s in appointment.appointment_services.all()
            )
            dt_end = dt_start + datetime.timedelta(minutes=total_duration)
            end_time = dt_end.time()

            appointments = (
                Appointment.objects.filter(
                    provider=provider, date=date, is_delete=False
                )
                .exclude(status__in=["cancelled", "rescheduled"])
                .exclude(pk=appointment.pk)
            )

            is_available = True
            for appt in appointments:
                appt_start = datetime.datetime.combine(date, appt.start_time)
                appt_start = timezone.make_aware(
                    appt_start, timezone.get_current_timezone()
                )
                appt_end = datetime.datetime.combine(date, appt.end_time)
                appt_end = timezone.make_aware(
                    appt_end, timezone.get_current_timezone()
                )
                if max(dt_start, appt_start) < min(dt_end, appt_end):
                    is_available = False
                    break

            if not is_available:
                messages.error(
                    self.request,
                    "We're sorry! This heavily trafficked time slot is booked. Please select a different time.",
                )
                return self.form_invalid(form)

            appointment.date = date
            appointment.start_time = start_time
            appointment.end_time = end_time
            appointment.status = "pending"
            appointment.save(update_fields=["date", "start_time", "end_time", "status"])

            send_booking_email(appointment, "rescheduled", self.request)

            return redirect(
                "guest_manage_appointment",
                booking_reference=appointment.booking_reference,
            )
