import datetime

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Appointment
from apps.bookings.services import BookingService, BookingVerificationError
from apps.services.models import Service, ServiceProvider


class BookingServiceTests(TestCase):
    def setUp(self):
        # Create Provider
        self.provider_user = User.objects.create_user(
            email="provider@test.com", password="pwd", role="provider"
        )
        self.provider = ServiceProvider.objects.create(
            user=self.provider_user, business_name="Test Spa"
        )

        # Create Dummy Service
        self.service = Service.objects.create(
            provider=self.provider, title="Massage", duration=60, price=100
        )

        # Build some appointments mapping out limits
        self.today = timezone.localtime().date()
        self.future_date = self.today + datetime.timedelta(days=2)

        # Appointment 1 from 09:00 to 10:00
        self.appt1 = Appointment.objects.create(
            provider=self.provider,
            date=self.future_date,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            status="confirmed",
            guest_email="guest1@test.com",
        )

    def test_overlap_identical_slot_denied(self):
        # Trying to book 09:00 to 10:00 should fail
        is_available = BookingService.is_slot_available(
            self.provider, self.future_date, datetime.time(9, 0), datetime.time(10, 0)
        )
        self.assertFalse(is_available)

    def test_overlap_partial_start_denied(self):
        # Trying to book 08:30 to 09:30 should fail
        is_available = BookingService.is_slot_available(
            self.provider, self.future_date, datetime.time(8, 30), datetime.time(9, 30)
        )
        self.assertFalse(is_available)

    def test_overlap_partial_end_denied(self):
        # Trying to book 09:30 to 10:30 should fail
        is_available = BookingService.is_slot_available(
            self.provider, self.future_date, datetime.time(9, 30), datetime.time(10, 30)
        )
        self.assertFalse(is_available)

    def test_no_overlap_adjacent_slots_allowed(self):
        # Booking 08:00 - 09:00 (exact overlap with bounds) is OK
        is_available = BookingService.is_slot_available(
            self.provider, self.future_date, datetime.time(8, 0), datetime.time(9, 0)
        )
        self.assertTrue(is_available)

        # Booking 10:00 - 11:00 is OK
        is_available = BookingService.is_slot_available(
            self.provider, self.future_date, datetime.time(10, 0), datetime.time(11, 0)
        )
        self.assertTrue(is_available)

    def test_time_constraint_too_soon_raises_err(self):
        now = timezone.now()
        # Appointment in 30 minutes
        dt_start = now + datetime.timedelta(minutes=30)

        with self.assertRaisesMessage(
            BookingVerificationError, "least 1 hour in advance"
        ):
            BookingService.check_time_constraints(dt_start.date(), dt_start.time(), 30)

    def test_time_constraint_too_far_raises_err(self):
        future_limit = timezone.now() + datetime.timedelta(days=91)

        with self.assertRaisesMessage(
            BookingVerificationError, "more than 90 days in advance"
        ):
            BookingService.check_time_constraints(
                future_limit.date(), future_limit.time(), 60
            )
