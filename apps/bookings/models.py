import datetime
import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.common.models import BaseModel
from apps.services.models import Service, ServiceProvider


class Appointment(BaseModel):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("rescheduled", "Rescheduled"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    )

    services = models.ManyToManyField(
        Service, through="AppointmentService", related_name="appointments"
    )
    provider = models.ForeignKey(
        ServiceProvider, on_delete=models.PROTECT, related_name="appointments"
    )

    # Optional registered user
    customer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_appointments",
    )

    # Guest Info
    guest_name = models.CharField(max_length=255, blank=True, null=True)
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone_number = PhoneNumberField(blank=True, null=True)

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    booking_reference = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True
    )

    @property
    def total_price(self):
        return sum(s.service_price for s in self.appointment_services.all())

    @property
    def can_be_modified_by_customer(self):
        if self.status in ["confirmed", "cancelled", "completed"]:
            return False

        dt_start = datetime.datetime.combine(self.date, self.start_time)
        dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())
        now = timezone.now()

        return not (dt_start < (now + datetime.timedelta(hours=24)))

    def __str__(self):
        name = self.customer_user.email if self.customer_user else self.guest_email
        return f"Appointment for {name} on {self.date} at {self.start_time}"


class AppointmentService(BaseModel):
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="appointment_services"
    )
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="appointment_services"
    )

    service_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Price of the service at time of booking"),
    )
    service_duration = models.PositiveIntegerField(
        help_text=_("Duration in minutes at time of booking")
    )

    def clean(self):
        super().clean()
        if (
            hasattr(self, "appointment")
            and hasattr(self, "service")
            and self.service.provider_id != self.appointment.provider_id
        ):
            raise ValidationError(
                f"Service '{self.service.title}' does not belong to provider '{self.appointment.provider.business_name}'."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service.title} for {self.appointment}"


auditlog.register(Appointment)
auditlog.register(AppointmentService)
