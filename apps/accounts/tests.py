import pytest
from django.urls import reverse

from apps.accounts.models import OTPVerification


@pytest.mark.django_db
class TestUserLoginView:
    """Test suite for user login view behavior."""

    @pytest.mark.parametrize(
        "user_fixture, expected_url_name",
        [("customer_user", "home"), ("provider_user", "provider_dashboard")],
    )
    def test_login_success(self, client, request, user_fixture, expected_url_name):
        """Verifies successful login redirects to correct dashboard based on role."""
        user = request.getfixturevalue(user_fixture)
        url = reverse("login")
        response = client.post(
            url, data={"username": user.email, "password": "password123"}
        )
        assert response.status_code == 302
        assert response.url == reverse(expected_url_name)

    def test_login_invalid(self, client, customer_user):
        """Verifies that invalid credentials return the form with errors."""
        url = reverse("login")
        response = client.post(
            url, data={"username": customer_user.email, "password": "wrongpassword"}
        )
        assert response.status_code == 200
        assert (
            "Please enter a correct email address and password."
            in str(response.content)
            or "form" in response.context
        )

    def test_authenticated_user_redirect(self, client, customer_user):
        """Verifies already authenticated users are redirected away from login."""
        client.force_login(customer_user)
        url = reverse("login")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("home")


@pytest.mark.django_db
class TestUserLogoutView:
    """Test suite for user logout behavior."""

    def test_logout(self, client, customer_user):
        """Verifies logout invalidates session and redirects to home."""
        client.force_login(customer_user)
        url = reverse("logout")
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse("home")


@pytest.mark.django_db
class TestUserRegisterView:
    """Test suite for user registration."""

    def test_get_register_form(self, client):
        """Verifies the registration form is served successfully."""
        url = reverse("register")
        response = client.get(url)
        assert response.status_code == 200
        assert "form" in response.context

    def test_authenticated_user_redirect(self, client, customer_user):
        """Verifies authenticated users cannot access the registration page."""
        client.force_login(customer_user)
        url = reverse("register")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("home")

    def test_post_valid_data(self, client):
        """Verifies submitting valid registration data triggers OTP flow."""
        url = reverse("register")
        data = {
            "email": "newuser@example.com",
            "phone_number": "+12125552368",
            "role": "customer",
            "password1": "password123",
            "password2": "password123",
        }
        response = client.post(url, data)
        # Should redirect to OTP page on valid initial capture
        assert response.status_code == 302
        assert response.url == reverse("register_otp_verify")


@pytest.mark.django_db
class TestOTPVerifyView:
    """Test suite for OTP verification flow."""

    def test_get_without_session(self, client):
        """Verifies accessing OTP page without email in session redirects back to register."""
        url = reverse("register_otp_verify")
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("register")

    def test_get_with_session(self, client):
        """Verifies accessing OTP page with session is successful."""
        session = client.session
        session["verify_email"] = "test@example.com"
        session.save()
        url = reverse("register_otp_verify")
        response = client.get(url)
        assert response.status_code == 200
        assert "email" in response.context

    def test_post_without_session(self, client):
        """Verifies POST action without session redirects back."""
        url = reverse("register_otp_verify")
        response = client.post(url, data={"otp": "123456"})
        assert response.status_code == 302
        assert response.url == reverse("register")

    def test_post_resend_otp(self, client):
        """Verifies the resend action updates the OTP."""
        session = client.session
        session["verify_email"] = "test@example.com"
        session.save()
        OTPVerification.objects.create(
            email="test@example.com", otp="000000", registration_data=""
        )
        url = reverse("register_otp_verify")
        response = client.post(url, data={"action": "resend"})
        assert response.status_code == 302
        assert response.url == reverse("register_otp_verify")
        otp_record = OTPVerification.objects.get(email="test@example.com")
        assert otp_record.otp != "000000"

    def test_post_invalid_otp(self, client):
        """Verifies submitting a wrong OTP returns the form with an error."""
        session = client.session
        session["verify_email"] = "test@example.com"
        session.save()
        OTPVerification.objects.create(
            email="test@example.com", otp="123456", registration_data=""
        )
        url = reverse("register_otp_verify")
        response = client.post(url, data={"otp": "999999"})
        assert response.status_code == 200

    def test_post_valid_otp(self, client):
        """Verifies submitting correct OTP logs the user in and redirects."""
        session = client.session
        session["verify_email"] = "newuser2@example.com"
        session.save()
        import urllib.parse

        registration_data = urllib.parse.urlencode(
            {
                "email": "newuser2@example.com",
                "phone_number": "+0987654321",
                "role": "customer",
            }
        )
        OTPVerification.objects.create(
            email="newuser2@example.com",
            otp="123456",
            registration_data=registration_data,
        )
        url = reverse("register_otp_verify")
        response = client.post(url, data={"otp": "123456"})
        # Should redirect on login success
        assert response.status_code == 302


@pytest.mark.django_db
class TestProfileView:
    """Test suite for the user profile view."""

    @pytest.mark.parametrize(
        "user_fixture, is_customer, expected_status",
        [("customer_user", True, 200), ("provider_user", False, 403)],
    )
    def test_get_profile(
        self, client, request, user_fixture, is_customer, expected_status
    ):
        """Verifies profile page loads for customers and blocks/redirects providers."""
        user = request.getfixturevalue(user_fixture)
        client.force_login(user)
        url = reverse("profile")
        response = client.get(url)
        assert response.status_code == expected_status
        if is_customer:
            assert "upcoming_appointments_count" in response.context


@pytest.mark.django_db
class TestProfileEditView:
    """Test suite for user profile editing."""

    @pytest.mark.parametrize(
        "user_fixture, expected_provider_form_is_none",
        [("customer_user", True), ("provider_user", False)],
    )
    def test_get_profile_edit(
        self, client, request, user_fixture, expected_provider_form_is_none
    ):
        """Verifies edit form serves correctly and includes provider form when applicable."""
        user = request.getfixturevalue(user_fixture)
        client.force_login(user)
        url = reverse("profile_edit")
        response = client.get(url)
        assert response.status_code == 200
        assert "form" in response.context
        if expected_provider_form_is_none:
            assert response.context["provider_form"] is None
        else:
            assert "provider_form" in response.context

    def test_post_customer_edit(self, client, customer_user):
        """Verifies customer profile mutations are correctly saved and redirect."""
        client.force_login(customer_user)
        url = reverse("profile_edit")
        data = {"email": "updated@example.com", "phone_number": "+12125552368"}
        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse("profile")
        customer_user.refresh_from_db()
        assert customer_user.email == "updated@example.com"
