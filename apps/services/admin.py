from django.contrib import admin

from .models import Service, ServiceProvider, WorkingHours

admin.site.register(ServiceProvider)
admin.site.register(Service)
admin.site.register(WorkingHours)
