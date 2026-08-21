from django.urls import path

from .views import (
    LandingPageView,
    ManageWorkingHoursView,
    ProviderDashboardView,
    ProviderDetailView,
    ServiceCreateView,
    ServiceDeleteView,
    ServiceListView,
    ServiceToggleActiveView,
    ServiceUpdateView,
)

urlpatterns = [
    path("", LandingPageView.as_view(), name="home"),
    path(
        "provider/dashboard/",
        ProviderDashboardView.as_view(),
        name="provider_dashboard",
    ),
    path(
        "provider/working-hours/",
        ManageWorkingHoursView.as_view(),
        name="manage_working_hours",
    ),
    path("provider/services/", ServiceListView.as_view(), name="service_list"),
    path("provider/services/add/", ServiceCreateView.as_view(), name="service_add"),
    path(
        "provider/services/<int:pk>/edit/",
        ServiceUpdateView.as_view(),
        name="service_edit",
    ),
    path(
        "provider/services/<int:pk>/delete/",
        ServiceDeleteView.as_view(),
        name="service_delete",
    ),
    path(
        "provider/services/<int:pk>/toggle-active/",
        ServiceToggleActiveView.as_view(),
        name="service_toggle_active",
    ),
    path("provider/<int:pk>/", ProviderDetailView.as_view(), name="provider_detail"),
]
