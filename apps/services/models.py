from auditlog.registry import auditlog
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel


class ServiceProvider(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_provider",
    )
    business_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    business_address = models.CharField(
        max_length=500, blank=True, help_text="Add your business physical location."
    )
    business_logo = models.ImageField(
        upload_to="provider_logos/", blank=True, null=True
    )

    def __str__(self):
        return self.business_name


class Service(BaseModel):
    provider = models.ForeignKey(
        ServiceProvider, on_delete=models.CASCADE, related_name="services"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="service_images/", blank=True, null=True)
    duration = models.PositiveIntegerField(help_text=_("Duration in minutes"))
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # is_active handles active status

    def get_future_bookings_count(self):
        today = timezone.localdate()
        return self.appointment_services.filter(
            appointment__date__gte=today,
            appointment__status__in=["pending", "confirmed", "rescheduled"],
        ).count()

    def __str__(self):
        return f"{self.title} - {self.provider.business_name}"


class WorkingHours(BaseModel):
    DAY_CHOICES = (
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    )
    provider = models.ForeignKey(
        ServiceProvider, on_delete=models.CASCADE, related_name="working_hours"
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_working_day = models.BooleanField(default=True)

    class Meta:
        unique_together = ("provider", "day_of_week")

    def __str__(self):
        return f"{self.provider.business_name} - {self.get_day_of_week_display()}"


auditlog.register(ServiceProvider)
auditlog.register(Service)
auditlog.register(WorkingHours)
