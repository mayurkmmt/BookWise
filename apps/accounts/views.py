import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import EmailMultiAlternatives
from django.http import QueryDict
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.generic import DetailView, View

from apps.accounts.forms import CustomUserCreationForm, UserProfileEditForm
from apps.accounts.models import OTPVerification, User
from apps.bookings.models import Appointment
from apps.common.mixins import CustomerRequiredMixin
from apps.services.forms import ServiceProviderForm
from apps.services.models import ServiceProvider


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_invalid(self, form):
        if "__all__" in form.errors:
            for error in form.errors["__all__"]:
                messages.error(self.request, error)
            del form.errors["__all__"]
        return super().form_invalid(form)

    def get_success_url(self):
        user = self.request.user
        if hasattr(user, "role") and user.role == "provider":
            return reverse_lazy("provider_dashboard")
        return reverse_lazy("home")


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("home")


class UserRegisterView(View):
    template_name = "accounts/register.html"
    form_class = CustomUserCreationForm

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return render(request, self.template_name, {"form": self.form_class()})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            otp = str(random.randint(100000, 999999))
            email = form.cleaned_data.get("email")

            OTPVerification.objects.update_or_create(
                email=email,
                defaults={"otp": otp, "registration_data": request.POST.urlencode()},
            )

            request.session["verify_email"] = email

            html_content = render_to_string(
                "emails/otp_notification.html",
                {
                    "otp": otp,
                    "preheader_message": "Welcome to BookWise! You are almost done.",
                },
            )
            text_content = strip_tags(html_content)

            msg = EmailMultiAlternatives(
                "Your BookWise Verification Code",
                text_content,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bookwisetest.com"),
                [email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)
            return redirect("register_otp_verify")
        return render(request, self.template_name, {"form": form})


class OTPVerifyView(View):
    template_name = "accounts/otp_verify.html"

    def get(self, request, *args, **kwargs):
        if "verify_email" not in request.session:
            return redirect("register")
        return render(
            request, self.template_name, {"email": request.session.get("verify_email")}
        )

    def post(self, request, *args, **kwargs):
        if "verify_email" not in request.session:
            return redirect("register")

        email = request.session["verify_email"]

        if request.POST.get("action") == "resend":
            otp = str(random.randint(100000, 999999))
            OTPVerification.objects.filter(email=email).update(otp=otp)

            html_content = render_to_string(
                "emails/otp_notification.html",
                {
                    "otp": otp,
                    "preheader_message": "Welcome to BookWise! You requested a new code.",
                },
            )
            text_content = strip_tags(html_content)

            msg = EmailMultiAlternatives(
                "Your New BookWise Verification Code",
                text_content,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bookwisetest.com"),
                [email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)

            messages.success(
                request, "A new verification code has been sent to your email."
            )
            return redirect("register_otp_verify")

        submitted_otp = request.POST.get("otp", "").strip()

        try:
            otp_record = OTPVerification.objects.get(email=email, otp=submitted_otp)
        except OTPVerification.DoesNotExist:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, self.template_name, {"email": email})

        post_data = QueryDict(otp_record.registration_data)

        form = CustomUserCreationForm(post_data)
        if form.is_valid():
            user = form.save()
            login(request, user)

            otp_record.delete()
            del request.session["verify_email"]

            messages.success(request, "Registration successful! Welcome aboard.")

            if getattr(user, "role", "") == "provider":
                return redirect("provider_dashboard")
            return redirect("home")
        else:
            messages.error(
                request,
                "We encountered a critical error reviving your registration form. Please try registering again.",
            )
            otp_record.delete()
            del request.session["verify_email"]
            return redirect("register")


class ProfileView(CustomerRequiredMixin, DetailView):
    model = User
    template_name = "accounts/profile.html"
    context_object_name = "user_profile"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        now = timezone.localtime().replace(tzinfo=None)

        # Pull un-deleted appointments uniquely constrained to the active login session
        appointments = Appointment.objects.filter(
            customer_user=self.request.user, is_delete=False
        )

        # Process and bind strict aggregates mapping to the grid UI specifications
        context["upcoming_appointments_count"] = appointments.filter(
            date__gte=now.date(),
            # status__in=['pending', 'confirmed']
        ).count()
        context["past_appointments_count"] = appointments.filter(
            date__lt=now.date()
        ).count()
        context["total_appointments_count"] = appointments.count()

        # Inject the active array tracing specifically just today's workload for the data table
        context["today_appointments"] = appointments.filter(date=now.date()).order_by(
            "start_time"
        )
        return context


class ProfileEditView(LoginRequiredMixin, View):
    template_name = "accounts/profile_edit.html"

    def get(self, request, *args, **kwargs):
        user_form = UserProfileEditForm(instance=request.user)
        provider_form = None
        if request.user.role == "provider":
            provider, _ = ServiceProvider.objects.get_or_create(
                user=request.user, defaults={"business_name": request.user.email}
            )
            provider_form = ServiceProviderForm(instance=provider)

        return render(
            request,
            self.template_name,
            {"form": user_form, "provider_form": provider_form},
        )

    def post(self, request, *args, **kwargs):
        user_form = UserProfileEditForm(request.POST, instance=request.user)
        provider_form = None
        if request.user.role == "provider":
            provider, _ = ServiceProvider.objects.get_or_create(user=request.user)
            provider_form = ServiceProviderForm(
                request.POST, request.FILES, instance=provider
            )

        if user_form.is_valid():
            if provider_form is not None:
                if provider_form.is_valid():
                    user_form.instance.modified_by = request.user
                    user_form.save()
                    provider_form.instance.modified_by = request.user
                    provider_form.save()
                    messages.success(
                        request, "Your business profile has been fully updated."
                    )
                    return redirect("profile_edit")
            else:
                user_form.instance.modified_by = request.user
                user_form.save()
                messages.success(request, "Your profile has been updated.")
                return redirect("profile")

        messages.error(request, "Please correct the errors below.")
        return render(
            request,
            self.template_name,
            {"form": user_form, "provider_form": provider_form},
        )
