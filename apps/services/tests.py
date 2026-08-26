import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.services.models import Service, WorkingHours


@pytest.mark.django_db
class TestLandingPageView:
    """Test suite handling search and display on the platform landing page."""

    @pytest.mark.parametrize(
        "query, expected_status",
        [("", 200), ("Test Business", 200), ("Nonexistent", 200)],
    )
    def test_landing_page(
        self, client, provider, active_service, query, expected_status
    ):
        """Verifies that the landing page accurately processes search term filters."""
        url = reverse("home")
        if query:
            url += f"?q={query}"
        response = client.get(url)
        assert response.status_code == expected_status
        if query == "Test Business":
            assert provider in response.context["providers"]
        elif query == "Nonexistent":
            assert provider not in response.context["providers"]


@pytest.mark.django_db
class TestProviderDetailView:
    """Test suite handling public details and capabilities for a specific provider."""

    @pytest.mark.parametrize(
        "query, expected_status",
        [("", 200), ("Test Service Active", 200), ("Nonexistent", 200)],
    )
    def test_provider_detail(
        self, client, provider, active_service, query, expected_status
    ):
        """Verifies provider pages successfully execute sub-filtering on offered services."""
        url = reverse("provider_detail", kwargs={"pk": provider.id})
        if query:
            url += f"?q={query}"
        response = client.get(url)
        assert response.status_code == expected_status
        assert response.context["provider"] == provider

        # Test pagination/service filtering
        page_obj_services = response.context["services"]
        if query == "Test Service Active":
            assert active_service in page_obj_services
        elif query == "Nonexistent":
            assert active_service not in page_obj_services


@pytest.mark.django_db
class TestProviderDashboardView:
    """Test suite handling authenticated provider access to dashboards."""

    def test_unauthenticated_access(self, client):
        """Verifies anonymous users are challenged for login on provider routes."""
        url = reverse("provider_dashboard")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.url

    def test_customer_access_denied(self, client, customer_user):
        """Verifies standard customer roles receive Forbidden responses securely."""
        client.force_login(customer_user)
        url = reverse("provider_dashboard")
        response = client.get(url)
        assert response.status_code == 403

    def test_provider_access_success(self, client, provider_user, provider):
        """Verifies authenticated providers successfully reach their UI panels."""
        client.force_login(provider_user)
        url = reverse("provider_dashboard")
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["provider"] == provider


@pytest.mark.django_db
class TestManageWorkingHoursView:
    """Test suite covering Working Hours CRUD and Provider configurations."""

    def test_get_working_hours(self, client, provider_user, provider):
        """Verifies the working hours UI loads the formset cleanly."""
        client.force_login(provider_user)
        url = reverse("manage_working_hours")
        response = client.get(url)
        assert response.status_code == 200
        assert "formset" in response.context

    def test_post_working_hours(self, client, provider_user, provider, working_hours):
        """Verifies editing working hours mutations execute and save to DB."""
        client.force_login(provider_user)
        url = reverse("manage_working_hours")

        data = {
            "working_hours-TOTAL_FORMS": "7",
            "working_hours-INITIAL_FORMS": "7",
            "working_hours-MIN_NUM_FORMS": "0",
            "working_hours-MAX_NUM_FORMS": "1000",
        }
        for i in range(7):
            wh_id = WorkingHours.objects.get(provider=provider, day_of_week=i).id
            data[f"working_hours-{i}-id"] = str(wh_id)
            data[f"working_hours-{i}-provider"] = str(provider.id)
            data[f"working_hours-{i}-day_of_week"] = str(i)
            # Modifying start time strictly for DB side-effect validation
            data[f"working_hours-{i}-start_time"] = "10:15:00"
            data[f"working_hours-{i}-end_time"] = "18:00:00"
            data[f"working_hours-{i}-is_working_day"] = "on"

        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse("manage_working_hours")

        # Strictly assert the DB values were updated safely
        sunday_hours = WorkingHours.objects.get(provider=provider, day_of_week=0)
        assert sunday_hours.start_time.hour == 10
        assert sunday_hours.start_time.minute == 15


@pytest.mark.django_db
class TestServiceCRUDViews:
    """Test suite controlling the standard views for Creating/Updating Providers Services."""

    # Generic valid tiny image for mocking
    TEST_GIF = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"

    def test_service_list_view(self, client, provider_user, active_service):
        """Verifies providers see their listed services successfully."""
        client.force_login(provider_user)
        url = reverse("service_list")
        response = client.get(url)
        assert response.status_code == 200
        assert active_service in response.context["services"]

    @pytest.mark.parametrize(
        "payload, expected_status, success",
        [
            (
                {
                    "title": "New Service Test",
                    "description": "Desc",
                    "price": "50.00",
                    "duration": "30",
                    "is_active": "True",
                },
                302,
                True,
            ),
            (
                {
                    "title": "",
                    "description": "Desc",
                    "price": "-5",
                    "duration": "0",
                    "is_active": "True",
                },
                200,
                False,
            ),
        ],
    )
    def test_service_create_view(
        self, client, provider_user, payload, expected_status, success, working_hours
    ):
        """Verifies services can be added under tight param validations."""
        client.force_login(provider_user)
        url = reverse("service_add")

        post_data = payload.copy()
        if expected_status == 302:
            post_data["image"] = SimpleUploadedFile(
                name="test_image.gif", content=self.TEST_GIF, content_type="image/gif"
            )

        response = client.post(url, data=post_data)
        assert response.status_code == expected_status
        if success:
            assert Service.objects.filter(title="New Service Test").exists()

    def test_service_update_view(
        self, client, provider_user, active_service, working_hours
    ):
        """Verifies service details are actively mutated inside DB when updated."""
        client.force_login(provider_user)
        url = reverse("service_edit", kwargs={"pk": active_service.id})

        test_image = SimpleUploadedFile(
            name="test_image.gif", content=self.TEST_GIF, content_type="image/gif"
        )
        response = client.post(
            url,
            data={
                "title": "Updated Service",
                "description": "Desc updated",
                "price": "75.00",
                "duration": "45",
                "is_active": "True",
                "image": test_image,
            },
        )
        assert response.status_code == 302
        active_service.refresh_from_db()
        assert active_service.title == "Updated Service"

    def test_service_delete_view_soft_delete(
        self, client, provider_user, inactive_service
    ):
        """Verifies records are not strictly lost when dropping services but just flagged."""
        client.force_login(provider_user)
        url = reverse("service_delete", kwargs={"pk": inactive_service.id})
        response = client.post(url)
        assert response.status_code == 302

        # Verify strictly DB presence AND flag explicitly without defensive IFs
        inactive_service.refresh_from_db()
        assert inactive_service.is_delete is True

    def test_service_toggle_active_view(self, client, provider_user, active_service):
        """Verifies boolean activation statuses pivot securely upon demand."""
        client.force_login(provider_user)
        url = reverse("service_toggle_active", kwargs={"pk": active_service.id})
        response = client.post(url)
        assert response.status_code == 200
        active_service.refresh_from_db()
        assert active_service.is_active is False
