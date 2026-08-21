from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class ProviderRequiredMixin(UserPassesTestMixin):
    """Enforce that the logged in user is a ServiceProvider."""

    def test_func(self):
        return (
            self.request.user.is_authenticated and self.request.user.role == "provider"
        )

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == "provider":
            from apps.services.models import ServiceProvider

            ServiceProvider.objects.get_or_create(
                user=request.user, defaults={"business_name": request.user.email}
            )
        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(
                "You must be a Service Provider to access this page."
            )
        return super().handle_no_permission()


class ProviderDataIsolationMixin:
    """Automatically filter querysets so providers only see their own data, excluding soft-deleted records."""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request.user, "service_provider"):
            return qs.filter(
                provider=self.request.user.service_provider, is_delete=False
            )
        return qs.none()


class CustomerRequiredMixin(UserPassesTestMixin):
    """Enforce that the logged in user is a Customer."""

    def test_func(self):
        return (
            self.request.user.is_authenticated and self.request.user.role == "customer"
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You must be a Customer to access this page.")
        return super().handle_no_permission()
