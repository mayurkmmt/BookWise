# BookWise

BookWise is a web-based appointment booking system designed for service providers (clinics, salons, consultants) to manage their availability, and for customers to seamlessly book appointments online.

## Features

- **Provider Management:** Service providers can set up their profiles, including business names, logos, and descriptions.
- **Service Management:** Providers can create, edit, and manage services with customizable pricing, durations, and images.
- **Dynamic Availability:** Booking slots are dynamically generated based on provider availability, checking their active working hours against existing appointments.
- **Guest Bookings:** Unregistered users can use a specialized guest workflow with OTP email validation to successfully book appointments. Guests can manage their bookings via a unique reference link.
- **Multi-Tenant Architecture:** Strict data isolation between providers. Providers can only see and manage their own data.
- **Audit Logging:** Every critical database action is tracked.
- **Role-Based Access Control:** Distinct roles for Customers, Providers, and Administrators.
- **Notifications:** Built-in email integration for appointment updates and confirmations.

## Technology Stack

- **Backend:** Django
- **Database:** PostgreSQL
- **Environment Management:** `uv`
- **UI:** Server-rendered templates
- **Auditing:** `django-auditlog`

## Getting Started

1. Clone the repository.
2. Ensure you have `uv` installed, then install dependencies:
   ```bash
   uv sync
   ```
3. Copy `.env.example` to `.env` and configure your Postgres credentials and email settings.
4. Run migrations:
   ```bash
   uv run manage.py migrate
   ```
5. Create a superuser to access the admin portal:
   ```bash
   uv run manage.py createsuperuser
   ```
6. Start the development server:
   ```bash
   uv run manage.py runserver
   ```
