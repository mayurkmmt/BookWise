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

## Project Previews

### Global

#### 1. Authentication & Welcome
Secure sign-in experience for existing users.

<img src="screenshots/login.png" alt="Log In" width="800" />

#### 2. Account Registration
Create a new account to access the platform.

<img src="screenshots/register.png" alt="Register" width="800" />

### Customer Experience

#### 1. Landing Page & Provider Search
*Discover providers and services on the main landing page.*
The main landing page features a directory and search functionality. Registered customers can search for specific providers or services to seamlessly filter and view the provider list accordingly.

<img src="screenshots/customer/01-landing-page.png" alt="Landing Page" width="800" />

#### 2. Provider Details & Services
*View comprehensive provider details and select the desired service.*
This screen appears when you click on any provider from the landing page. It displays comprehensive details about the provider along with a list of their offered services, allowing you to easily select a service and book an appointment.

<img src="screenshots/customer/02-provider-details-with-services.png" alt="Provider Details" width="800" />

#### 3. Customer Booking Process
*Seamlessly select dates for your appointment.*
During the booking process, registered customers select a date to view the available time slots for that day. Unlike guest users, your personal details are securely pre-filled from your profile for a faster checkout experience.

<img src="screenshots/customer/03-customer-user-booking.png" alt="Customer Booking" width="800" />

#### 4. Booking Confirmation
*Your appointment request is successfully sent.*
The booking process is complete, and your appointment request has been successfully delivered to the service provider.

<img src="screenshots/customer/04-booking-send-to-service-provider.png" alt="Booking Confirmation" width="800" />

#### 5. Customer Dashboard
*Overview of your upcoming and past appointments.*
The customer dashboard provides a high-level visual overview of your account activity, including quick access to your most recent and upcoming bookings.

<img src="screenshots/customer/05-dashboard.png" alt="Dashboard" width="800" />

#### 6. Booking List
*Track all your scheduled services.*
This page displays a comprehensive list of all past, active, and upcoming appointments, allowing you to easily monitor your schedule.

<img src="screenshots/customer/06-booking-list.png" alt="Booking List" width="800" />

#### 7. Booking Details
*View specific details for a selected appointment.*
You can click on any specific booking to view in-depth details, including provider contact information, selected services, and exact times.

<img src="screenshots/customer/07-booking-details.png" alt="Booking Details" width="800" />

#### 8. Rescheduling
*Adapt your schedule when plans change.*
If plans change, you can seamlessly reschedule your existing appointments to a new available date and time slot without having to cancel and rebook.

<img src="screenshots/customer/08-booking-reschedule.png" alt="Reschedule Booking" width="800" />

#### 9. Settings
*Manage your profile and account preferences.*
The settings page allows you to manage your profile information, update contact details, and configure your personal account preferences.

<img src="screenshots/customer/09-settings.png" alt="Settings" width="800" />

### Guest Experience

#### 1. Landing Page & Provider Search
*Discover providers and services on the main landing page.*
The main landing page features a directory and search functionality. You can search for specific providers or services to seamlessly filter and view the provider list accordingly.

<img src="screenshots/guest_user/01-landing-page.png" alt="Landing Page" width="800" />

#### 2. Provider Details & Services
*View comprehensive provider details and select the desired service.*
This screen appears when you click on any provider from the landing page. It displays comprehensive details about the provider along with a list of their offered services, allowing you to easily select a service and book an appointment.

<img src="screenshots/guest_user/02-provider-details-with-services.png" alt="Provider Details" width="800" />

#### 3. Guest Booking Process
*Seamlessly select dates and fill in basic details.*
During the booking process, you select a date to view the available time slots for that day. As a guest user, you will then need to provide your full name, email, and phone number. Upon confirming the booking, you are navigated to the OTP verification screen.

<img src="screenshots/guest_user/03-guest-user-booking.png" alt="Guest Booking" width="800" />

#### 4. OTP Verification
*Secure your booking by verifying your email address.*
This step handles email verification for guest users. Once you enter a valid OTP and click to finalize the secure booking, you are redirected to a confirmation page indicating that the booking request has been sent.

<img src="screenshots/guest_user/04-confirm-booking-with-otp.png" alt="OTP Verification" width="800" />

#### 5. Booking Confirmation
*Your appointment request is successfully sent.*
The booking process is complete, and your appointment request has been successfully delivered to the service provider.

<img src="screenshots/guest_user/05-booking-send-to-service-provider.png" alt="Booking Sent" width="800" />

### Service Provider Dashboard

#### 1. Dashboard Overview
*High-level summary of your business activities.*
The service provider dashboard provides a comprehensive visual summary of your daily schedule, recent bookings, and overall business metrics at a glance.

<img src="screenshots/service_provider/01-dashboard.png" alt="Dashboard Overview" width="800" />

#### 2. Appointment List
*Track and manage all your scheduled bookings.*
This screen displays a comprehensive list of all past, active, and upcoming appointments, allowing providers to easily track and filter their booking schedule.

<img src="screenshots/service_provider/02-appointment-list.png" alt="Appointment List" width="800" />

#### 3. Appointment Details
*In-depth view of a specific booking.*
Clicking on any appointment reveals the full details, including customer contact information, selected services, and exact appointment timing.

<img src="screenshots/service_provider/03-appointment-details.png" alt="Appointment Details" width="800" />

#### 4. Customer Directory
*Access your complete client base.*
This page features a directory of all clients who have booked with you, making it easy to search for and manage your customer relationships.

<img src="screenshots/service_provider/04-customer-list.png" alt="Customer Directory" width="800" />

#### 5. Customer Details
*View individual client history.*
Here you can dive into a specific customer's profile to view their detailed contact information and a complete history of their past and upcoming appointments with you.

<img src="screenshots/service_provider/05-customer-details.png" alt="Customer Details" width="800" />

#### 6. Service Management
*Comprehensive view of all services you offer.*
This screen lists all the active services you currently provide, giving you an easy way to oversee your offerings and their associated pricing.

<img src="screenshots/service_provider/06-service-list.png" alt="Service Management" width="800" />

#### 7. Add New Service
*Expand your business offerings.*
Providers can easily create new services by specifying necessary details such as the service name, description, duration, price and image.

<img src="screenshots/service_provider/07-add-service.png" alt="Add New Service" width="800" />

#### 8. Update Services
*Modify existing services as your business evolves.*
This interface allows you to select an existing service and seamlessly update its details, duration, or pricing to keep your offerings up to date.

<img src="screenshots/service_provider/08-update-services.png" alt="Update Services" width="800" />

#### 9. Delete Service
*Remove services you no longer provide.*
This screen ensures a secure process for deleting a service from your offerings, prompting a confirmation to prevent accidental removals.

<img src="screenshots/service_provider/09-delete-service.png" alt="Delete Service" width="800" />

#### 10. Manage Working Hours
*Define your availability for appointments.*
Here you can set your weekly working hours and breaks. The system uses this exact availability to automatically generate selectable time slots for your customers.

<img src="screenshots/service_provider/10-manage-working-hours.png" alt="Manage Working Hours" width="800" />

#### 11. Provider Settings
*Configure your provider profile and system preferences.*
The settings page lets you manage your business profile, update your logo and description, and other account preferences.

<img src="screenshots/service_provider/11-settings.png" alt="Provider Settings" width="800" />
