import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Appointment
from apps.bookings.services import BookingService, BookingVerificationError


@pytest.mark.django_db
class TestBookingService:
    """Test suite for core booking availability logic."""

    @pytest.mark.parametrize(
        "offset_hours, offset_days, expected_error",
        [
            (2, 0, False),  # Valid: 2 hours in advance minimum
            (0.5, 0, True),  # Invalid: strictly under 2 hour lead time
            (0, 91, True),  # Invalid: attempts to book > 90 days out
            (0, 10, False),  # Valid: comfortably within 90 days
        ],
    )
    def test_check_time_constraints(self, offset_hours, offset_days, expected_error):
        """Verifies limits against too-soon and too-far-out bookings."""
        target = timezone.localtime() + datetime.timedelta(
            hours=offset_hours, days=offset_days
        )
        target_date = target.date()
        target_time = target.time()

        if expected_error:
            with pytest.raises(BookingVerificationError):
                BookingService.check_time_constraints(target_date, target_time, 60)
        else:
            end_time = BookingService.check_time_constraints(
                target_date, target_time, 60
            )
            expected_end = (target + datetime.timedelta(minutes=60)).time()
            assert (
                end_time.hour == expected_end.hour
                and end_time.minute == expected_end.minute
            )

    def test_is_slot_available(self, provider, test_service):
        """Verifies slot availability checks properly query overlapping appointments."""
        target_date = timezone.localtime().date() + datetime.timedelta(days=1)
        start_time = datetime.time(10, 0)
        end_time = datetime.time(11, 0)

        assert (
            BookingService.is_slot_available(
                provider, target_date, start_time, end_time
            )
            is True
        )

        Appointment.objects.create(
            provider=provider,
            date=target_date,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(11, 30),
            status="pending",
        )

        assert (
            BookingService.is_slot_available(
                provider, target_date, start_time, end_time
            )
            is False
        )

    def test_process_authenticated_booking(
        self, customer_user, provider, test_service, working_hours
    ):
        """Verifies authenticated booking successfully constructs the Appointment instance."""
        target_date = timezone.localtime().date() + datetime.timedelta(days=1)
        start_time = datetime.time(10, 0)

        class DummyRequest:
            pass

        appointment = BookingService.process_authenticated_booking(
            user=customer_user,
            provider_id=provider.id,
            services=[test_service],
            date=target_date,
            start_time=start_time,
            request=DummyRequest(),
        )

        assert appointment.id is not None
        assert appointment.status == "pending"
        assert appointment.customer_user == customer_user


@pytest.mark.django_db
class TestBookingAPIViews:
    """Test suite for JSON-based Booking API endpoints."""

    @pytest.mark.parametrize(
        "query_params, expected_status",
        [
            ({"duration": "60"}, 400),
            ({}, 400),
            ({"date": "invalid", "duration": "60"}, 400),
        ],
    )
    def test_service_available_times_errors(
        self, client, provider, query_params, expected_status
    ):
        """Verifies API errors appropriately on malformed params."""
        url = reverse("api_available_times", kwargs={"provider_id": provider.id})
        response = client.get(url, query_params)
        assert response.status_code == expected_status

    def test_service_available_times_success(self, client, provider, working_hours):
        """Verifies proper retrieval of available booking slots."""
        target_date = (
            (timezone.localtime() + datetime.timedelta(days=1)).date().isoformat()
        )
        url = reverse("api_available_times", kwargs={"provider_id": provider.id})
        response = client.get(url, {"date": target_date, "duration": "60"})
        assert response.status_code == 200
        assert "slots" in response.json()


@pytest.mark.django_db
class TestCustomerBookingEngineView:
    """Test suite for the primary UI booking engine."""

    def test_get_booking_wizard(self, client, customer_user, provider, test_service):
        """Verifies booking wizard loads correctly."""
        client.force_login(customer_user)
        url = reverse("book_services", kwargs={"provider_id": provider.id})
        response = client.get(url, {"service": test_service.id})
        assert response.status_code == 200
        assert "services" in response.context

    def test_provider_redirect(self, client, provider_user, provider):
        """Verifies providers cannot utilize the booking engine."""
        client.force_login(provider_user)
        url = reverse("book_services", kwargs={"provider_id": provider.id})
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("home")


@pytest.fixture
def test_appointment(db, customer_user, provider):
    """Generates an upcoming appointment for listing tests."""
    return Appointment.objects.create(
        provider=provider,
        customer_user=customer_user,
        date=timezone.localtime().date() + datetime.timedelta(days=1),
        start_time=datetime.time(10, 0),
        end_time=datetime.time(11, 0),
        status="pending",
    )


@pytest.mark.django_db
class TestCustomerAppointmentListView:
    """Test suite for the customer schedule listing view."""

    def test_get_appointments(self, client, customer_user, test_appointment):
        """Verifies customers can view their appointments."""
        client.force_login(customer_user)
        url = reverse("customer_appointments")
        response = client.get(url)
        assert response.status_code == 200
        assert test_appointment in response.context["appointments"]

    def test_provider_access_denied(self, client, provider_user):
        """Verifies providers are blocked from accessing customer lists."""
        client.force_login(provider_user)
        url = reverse("customer_appointments")
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestProviderAppointmentListView:
    """Test suite for the provider calendar listing view."""

    def test_get_appointments(self, client, provider_user, test_appointment):
        """Verifies providers can securely load their appointment tracking view."""
        client.force_login(provider_user)
        url = reverse("provider_appointments")
        response = client.get(url)
        assert response.status_code == 200
        assert test_appointment in response.context["appointments"]

    def test_customer_access_denied(self, client, customer_user):
        """Verifies customers are blocked from accessing provider dashboards."""
        client.force_login(customer_user)
        url = reverse("provider_appointments")
        response = client.get(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestGuestBookingOTPVerifyView:
    """Test suite for unauthenticated guest appointment authorization loop."""

    def test_get_without_session(self, client):
        """Verifies attempting to access OTP without an email redirect drops you out."""
        url = reverse("guest_otp_verify")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_get_with_session(self, client):
        """Verifies standard access generates valid prompt."""
        session = client.session
        session["guest_booking_email"] = "guest@example.com"
        session.save()
        url = reverse("guest_otp_verify")
        response = client.get(url)
        assert response.status_code == 200
