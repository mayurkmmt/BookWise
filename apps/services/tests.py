from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Service, ServiceProvider

User = get_user_model()


class SearchTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            email="test1@example.com", password="password"
        )
        self.user2 = User.objects.create_user(
            email="test2@example.com", password="password"
        )

        self.provider1 = ServiceProvider.objects.create(
            user=self.user1,
            business_name="Alpha Hair Spa",
            is_active=True,
        )
        self.provider2 = ServiceProvider.objects.create(
            user=self.user2,
            business_name="Beta Massage Center",
            is_active=True,
        )

        self.service1 = Service.objects.create(
            provider=self.provider1,
            title="Haircut Basic",
            duration=30,
            price=20.00,
            is_active=True,
        )
        self.service2 = Service.objects.create(
            provider=self.provider1,
            title="Haircut Premium",
            duration=60,
            price=50.00,
            is_active=True,
        )
        self.service3 = Service.objects.create(
            provider=self.provider2,
            title="Deep Tissue Massage",
            duration=60,
            price=80.00,
            is_active=True,
        )

    def test_landing_page_search_by_provider_name(self):
        url = reverse("home")
        response = self.client.get(url, {"q": "Alpha"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.provider1, response.context["providers"])
        self.assertNotIn(self.provider2, response.context["providers"])

    def test_landing_page_search_by_service_name(self):
        url = reverse("home")
        response = self.client.get(url, {"q": "Massage"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.provider2, response.context["providers"])
        self.assertNotIn(self.provider1, response.context["providers"])

    def test_landing_page_search_no_results(self):
        url = reverse("home")
        response = self.client.get(url, {"q": "NonExistent"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["providers"]), 0)

    def test_provider_detail_search_by_service_name(self):
        url = reverse("provider_detail", args=[self.provider1.pk])
        response = self.client.get(url, {"q": "Premium"})
        self.assertEqual(response.status_code, 200)
        services = response.context["services"].object_list
        self.assertIn(self.service2, services)
        self.assertNotIn(self.service1, services)

    def test_provider_detail_search_no_results(self):
        url = reverse("provider_detail", args=[self.provider1.pk])
        response = self.client.get(url, {"q": "Massage"})
        self.assertEqual(response.status_code, 200)
        services = response.context["services"].object_list
        self.assertEqual(len(services), 0)
