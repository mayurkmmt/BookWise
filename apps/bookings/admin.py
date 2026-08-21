from django.contrib import admin

from .models import Appointment, AppointmentService

admin.site.register(Appointment)
admin.site.register(AppointmentService)
