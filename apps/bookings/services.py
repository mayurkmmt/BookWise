import datetime
import json
import random
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from apps.accounts.models import OTPVerification, User
from apps.bookings.models import Appointment, AppointmentService
from apps.bookings.utils import send_booking_email
from apps.services.models import Service, ServiceProvider


class BookingVerificationError(Exception):
    pass


class BookingService:
    @staticmethod
    def check_time_constraints(
        date: datetime.date,
        start_time: datetime.time,
        total_duration_minutes: int,
        is_reschedule: bool = False,
    ) -> datetime.time:
        """
        Validates the advance booking limits (e.g., must be 1 hour in advance max 90 days).
        Returns end_time if valid, raises BookingVerificationError if invalid.
        """
        now = timezone.now()
        dt_start = datetime.datetime.combine(date, start_time)
        if timezone.is_naive(dt_start):
            dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())

        if dt_start < (now + datetime.timedelta(minutes=59)):
            raise BookingVerificationError(
                "Appointments must be booked at least 1 hour in advance."
            )

        if dt_start > (now + datetime.timedelta(days=90)):
            verb = "rescheduled" if is_reschedule else "booked"
            raise BookingVerificationError(
                f"Appointments cannot be {verb} more than 90 days in advance to protect provider availability."
            )

        dt_end = dt_start + datetime.timedelta(minutes=total_duration_minutes)
        return dt_end.time()

    @staticmethod
    def is_slot_available(
        provider: ServiceProvider,
        date: datetime.date,
        start_time: datetime.time,
        end_time: datetime.time,
        exclude_appointment_id: int | None = None,
    ) -> bool:
        """
        Checks if the requested slot overlaps with any active appointments using DB queries.
        """
        overlapping_appointments = Appointment.objects.filter(
            provider=provider,
            date=date,
            is_delete=False,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exclude(status__in=["cancelled", "rescheduled"])

        if exclude_appointment_id:
            overlapping_appointments = overlapping_appointments.exclude(
                pk=exclude_appointment_id
            )

        return not overlapping_appointments.exists()

    @staticmethod
    @transaction.atomic
    def process_authenticated_booking(
        user: User,
        provider_id: int,
        services: list[Service],
        date: datetime.date,
        start_time: datetime.time,
        request: HttpRequest,
    ) -> Appointment:

        provider = ServiceProvider.objects.select_for_update().get(pk=provider_id)
        if not services:
            raise BookingVerificationError("No valid services selected.")

        total_duration = sum(s.duration for s in services)
        end_time = BookingService.check_time_constraints(
            date, start_time, total_duration
        )

        if not BookingService.is_slot_available(provider, date, start_time, end_time):
            raise BookingVerificationError(
                "We're sorry! This heavily trafficked time slot was just booked by another user. Please select a different time."
            )

        appointment = Appointment(
            provider=provider,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status="pending",
            customer_user=user,
            created_by=user,
            modified_by=user,
        )
        appointment.save()

        for s in services:
            AppointmentService.objects.create(
                appointment=appointment,
                service=s,
                service_price=s.price,
                service_duration=s.duration,
                created_by=user,
                modified_by=user,
            )

        # Dispatch email post-commit to avoid slow I/O blocking the database transaction lock
        transaction.on_commit(
            lambda: send_booking_email(appointment, "booked", request)
        )
        return appointment

    @staticmethod
    def process_guest_booking_intent(
        provider_id: int,
        services: list[Service],
        date: datetime.date,
        start_time: datetime.time,
        guest_name: str,
        guest_email: str,
        guest_phone_number: str | None,
        request: HttpRequest,
    ) -> None:
        provider = ServiceProvider.objects.get(pk=provider_id)
        if not services:
            raise BookingVerificationError("No valid services selected.")

        if not guest_name or not guest_email:
            raise BookingVerificationError("Guest bookings require a Name and Email.")

        if User.objects.filter(
            email=guest_email, role__in=["provider", "admin"]
        ).exists():
            raise BookingVerificationError(
                "Error: This email address is registered as a Provider or Admin account and cannot be used to instantly book services."
            )

        total_duration = sum(s.duration for s in services)
        end_time = BookingService.check_time_constraints(
            date, start_time, total_duration
        )

        # Verify slot roughly so we don't send OTP if booked, though the strict check will happen on verify.
        if not BookingService.is_slot_available(provider, date, start_time, end_time):
            raise BookingVerificationError(
                "We're sorry! This highly requested time slot is unavailable. Please select a different time."
            )

        otp = str(random.randint(100000, 999999))
        booking_payload = {
            "provider_id": provider.id,
            "service_ids": [s.id for s in services],
            "date": date.isoformat(),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "guest_name": guest_name,
            "guest_email": guest_email,
            "guest_phone_number": str(guest_phone_number) if guest_phone_number else "",
        }

        OTPVerification.objects.update_or_create(
            email=guest_email,
            defaults={"otp": otp, "registration_data": json.dumps(booking_payload)},
        )
        request.session["guest_booking_email"] = guest_email

        html_content = render_to_string(
            "emails/otp_notification.html",
            {
                "otp": otp,
                "preheader_message": "Verify your email to finalize your secure booking.",
            },
        )
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            "BookWise: Verify Your Secure Booking",
            text_content,
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bookwisetest.com"),
            [guest_email],
        )
        msg.attach_alternative(html_content, "text/html")
        # Send immediately since DB isn't locked on guest intent
        threading.Thread(target=msg.send, kwargs={"fail_silently": True}).start()

    @staticmethod
    @transaction.atomic
    def reschedule_appointment(
        appointment: Appointment,
        date: datetime.date,
        start_time: datetime.time,
        user: User,
        request: HttpRequest,
    ) -> Appointment:

        provider = ServiceProvider.objects.select_for_update().get(
            pk=appointment.provider.pk
        )

        total_duration = sum(
            s.service_duration for s in appointment.appointment_services.all()
        )
        end_time = BookingService.check_time_constraints(
            date, start_time, total_duration, is_reschedule=True
        )

        if not BookingService.is_slot_available(
            provider, date, start_time, end_time, exclude_appointment_id=appointment.pk
        ):
            raise BookingVerificationError(
                "We're sorry! This heavily trafficked time slot is booked. Please select a different time."
            )

        appointment.date = date
        appointment.start_time = start_time
        appointment.end_time = end_time
        appointment.status = "pending"
        appointment.modified_by = user
        appointment.save(
            update_fields=["date", "start_time", "end_time", "status", "modified_by"]
        )

        transaction.on_commit(
            lambda: send_booking_email(appointment, "rescheduled", request)
        )
        return appointment
