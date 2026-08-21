from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.accounts.models import User


class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[
            ("customer", "Customer"),
            ("provider", "Service Provider"),
        ],
        initial="customer",
        help_text="Select whether you are booking appointments or providing services.",
    )

    class Meta:
        model = User
        fields = ("email", "phone_number", "role")

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            raise forms.ValidationError("A valid phone number is absolutely required.")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if role not in ["customer", "provider"]:
            raise forms.ValidationError(
                "Invalid role selected. Super Admins cannot be created via this form."
            )
        return role


class UserProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email", "phone_number")

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            raise forms.ValidationError("A valid phone number is required.")
        return phone_number
