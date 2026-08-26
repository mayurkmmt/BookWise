import datetime

import pytest

from apps.accounts.models import User
from apps.services.models import Service, ServiceProvider, WorkingHours


@pytest.fixture
def customer_user(db):
    """Creates a basic customer user account for testing."""
    return User.objects.create_user(
        email="customer@example.com",
        password="password123",
        role="customer",
        phone_number="+1234567890",
    )


@pytest.fixture
def provider_user(db):
    """Creates a provider user account for testing."""
    return User.objects.create_user(
        email="provider@example.com",
        password="password123",
        role="provider",
        phone_number="+1987654321",
    )


@pytest.fixture
def provider(db, provider_user):
    """Creates a ServiceProvider tied to the provider_user."""
    return ServiceProvider.objects.create(
        user=provider_user, business_name="Test Business"
    )


@pytest.fixture
def active_service(db, provider):
    """Creates a randomly mock active Service."""
    return Service.objects.create(
        provider=provider,
        title="Test Service Active",
        description="Desc",
        price=100.0,
        duration=60,
        is_active=True,
    )


@pytest.fixture
def test_service(db, provider):
    """Creates a generic test Service (alias of active_service without 'Active' suffix)."""
    return Service.objects.create(
        provider=provider,
        title="Test Service",
        description="Desc",
        price=100.0,
        duration=60,
        is_active=True,
    )


@pytest.fixture
def inactive_service(db, provider):
    """Creates an inactive service for soft-delete/toggle tests."""
    return Service.objects.create(
        provider=provider,
        title="Test Service Inactive",
        description="Desc",
        price=100.0,
        duration=60,
        is_active=False,
    )


@pytest.fixture
def working_hours(db, provider):
    """Populates basic 9 to 5 working hours for all 7 days for the provider."""
    # Using bulk_create for better setup performance
    hours = [
        WorkingHours(
            provider=provider,
            day_of_week=i,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
            is_working_day=True,
        )
        for i in range(7)
    ]
    WorkingHours.objects.bulk_create(hours)
