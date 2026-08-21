from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.common.mixins import ProviderDataIsolationMixin, ProviderRequiredMixin
from apps.services.models import Service, ServiceProvider, WorkingHours

from .forms import ServiceForm, WorkingHoursFormSet


class LandingPageView(ListView):
    model = ServiceProvider
    template_name = "home.html"
    context_object_name = "providers"
    paginate_by = 12

    def get_queryset(self):
        queryset = ServiceProvider.objects.filter(is_active=True, is_delete=False)
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(business_name__icontains=q)
                | Q(
                    services__title__icontains=q,
                    services__is_active=True,
                    services__is_delete=False,
                )
            ).distinct()
        return queryset.order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        context["filter_query_string"] = (
            f"&{query_params.urlencode()}" if query_params else ""
        )
        return context


class ProviderDetailView(DetailView):
    model = ServiceProvider
    template_name = "provider/detail.html"
    context_object_name = "provider"

    def get_queryset(self):
        return ServiceProvider.objects.filter(is_active=True, is_delete=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services_qs = self.object.services.filter(
            is_active=True, is_delete=False
        ).order_by("-id")

        q = self.request.GET.get("q")
        if q:
            services_qs = services_qs.filter(title__icontains=q)

        paginator = Paginator(services_qs, 12)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["services"] = page_obj
        context["page_obj"] = page_obj

        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        context["filter_query_string"] = (
            f"&{query_params.urlencode()}" if query_params else ""
        )

        context["working_hours"] = self.object.working_hours.all().order_by(
            "day_of_week"
        )
        return context


class ProviderDashboardView(LoginRequiredMixin, ProviderRequiredMixin, TemplateView):
    template_name = "provider/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provider = getattr(self.request.user, "service_provider", None)
        context["provider"] = provider
        if provider:
            context["services_count"] = provider.services.filter(
                is_delete=False
            ).count()
            context["appointments_count"] = provider.appointments.filter(
                is_delete=False
            ).count()

            context["pending_count"] = provider.appointments.filter(
                status="pending", is_delete=False
            ).count()

            today_appointments = provider.appointments.filter(
                is_delete=False, date=timezone.localdate()
            ).order_by("start_time")
            context["today_appointments"] = today_appointments
            total_revenue = today_appointments.exclude(status="cancelled").aggregate(
                total=Sum("appointment_services__service_price")
            )["total"]
            context["today_revenue"] = total_revenue or 0
        return context


class ManageWorkingHoursView(ProviderRequiredMixin, View):
    template_name = "provider/working_hours.html"

    def get_provider(self):
        provider, _created = ServiceProvider.objects.get_or_create(
            user=self.request.user, defaults={"business_name": self.request.user.email}
        )
        if not provider.working_hours.exists():
            self.ensure_default_hours(provider)
        return provider

    def ensure_default_hours(self, provider):
        existing_days = provider.working_hours.values_list("day_of_week", flat=True)
        # Create missing days if they don't exist
        for day_int, day_name in WorkingHours.DAY_CHOICES:
            if day_int not in existing_days:
                WorkingHours.objects.create(
                    provider=provider,
                    day_of_week=day_int,
                    start_time="09:00",
                    end_time="17:00",
                    is_working_day=day_int < 5,
                    created_by=self.request.user,
                    modified_by=self.request.user,
                )

    def get(self, request):
        provider = self.get_provider()

        queryset = provider.working_hours.all().order_by("day_of_week")
        formset = WorkingHoursFormSet(instance=provider, queryset=queryset)

        return render(
            request, self.template_name, {"formset": formset, "provider": provider}
        )

    def post(self, request):
        provider = self.get_provider()
        queryset = provider.working_hours.all().order_by("day_of_week")
        formset = WorkingHoursFormSet(
            request.POST, instance=provider, queryset=queryset
        )

        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.id:
                    instance.created_by = request.user
                instance.modified_by = request.user
                instance.save()
            messages.success(
                request, "Your working hours schedule has been successfully updated."
            )
            return redirect("manage_working_hours")

        messages.error(request, "There was an error updating your schedule.")
        return render(
            request, self.template_name, {"formset": formset, "provider": provider}
        )


class ServiceListView(ProviderRequiredMixin, ProviderDataIsolationMixin, ListView):
    model = Service
    template_name = "provider/service_list.html"
    context_object_name = "services"
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        if "page" in query_params:
            del query_params["page"]
        context["filter_query_string"] = (
            f"&{query_params.urlencode()}" if query_params else ""
        )
        return context


class ServiceCreateView(ProviderRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = "provider/service_form.html"
    success_url = reverse_lazy("service_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["provider"] = getattr(self.request.user, "service_provider", None)
        return kwargs

    def form_valid(self, form):
        provider = getattr(self.request.user, "service_provider", None)
        form.instance.provider = provider
        form.instance.created_by = self.request.user
        form.instance.modified_by = self.request.user
        messages.success(self.request, "Service successfully created!")
        return super().form_valid(form)


class ServiceUpdateView(ProviderRequiredMixin, ProviderDataIsolationMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = "provider/service_form.html"
    success_url = reverse_lazy("service_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["provider"] = getattr(self.request.user, "service_provider", None)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context["future_bookings_count"] = self.object.appointment_services.filter(
            appointment__date__gte=today,
            appointment__status__in=["pending", "confirmed", "rescheduled"],
        ).count()
        return context

    def form_valid(self, form):
        form.instance.modified_by = self.request.user
        messages.success(self.request, "Service successfully updated!")
        return super().form_valid(form)


class ServiceToggleActiveView(ProviderRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        try:
            with transaction.atomic():
                service = Service.objects.select_for_update().get(
                    pk=pk, provider=request.user.service_provider, is_delete=False
                )
                service.is_active = not service.is_active
                service.modified_by = request.user
                service.save(update_fields=["is_active", "modified_by"])
            return JsonResponse({"status": "success", "is_active": service.is_active})
        except Service.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Service not found or unauthorized"},
                status=403,
            )


class ServiceDeleteView(ProviderRequiredMixin, ProviderDataIsolationMixin, DeleteView):
    model = Service
    template_name = "provider/service_confirm_delete.html"
    success_url = reverse_lazy("service_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context["future_bookings_count"] = self.object.appointment_services.filter(
            appointment__date__gte=today,
            appointment__status__in=["pending", "confirmed", "rescheduled"],
        ).count()
        return context

    def form_valid(self, form):
        messages.success(self.request, "Service successfully deleted.")
        return super().form_valid(form)
