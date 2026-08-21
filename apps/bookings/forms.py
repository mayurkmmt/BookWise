from django import forms
from phonenumber_field.formfields import PhoneNumberField

from apps.accounts.models import User


class BookingForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.is_reschedule = kwargs.pop("is_reschedule", False)
        super().__init__(*args, **kwargs)

        # Inject HTML5 required properties explicitly when in guest mode
        if not self.request or not self.request.user.is_authenticated:
            self.fields["guest_name"].required = True
            self.fields["guest_email"].required = True
            self.fields["guest_phone_number"].required = True

    date = forms.DateField(widget=forms.HiddenInput(attrs={"id": "id_date_hidden"}))
    start_time = forms.TimeField(
        widget=forms.HiddenInput(attrs={"id": "id_start_time_hidden"})
    )

    guest_name = forms.CharField(
        label="Full Name",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. John Doe"}),
    )
    guest_email = forms.EmailField(
        label="Email Address",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "john@example.com"}),
    )
    guest_phone_number = PhoneNumberField(
        label="Phone Number", required=False, region="US"
    )

    def clean(self):
        cleaned_data = super().clean()

        is_guest = not self.request or not self.request.user.is_authenticated

        if is_guest:
            guest_name = cleaned_data.get("guest_name")
            guest_email = cleaned_data.get("guest_email")
            guest_phone = cleaned_data.get("guest_phone_number")

            if not guest_name:
                self.add_error("guest_name", "Full Name is required.")

            if not guest_email:
                self.add_error("guest_email", "Email Address is required.")
            elif (
                not self.is_reschedule
                and User.objects.filter(email__iexact=guest_email).exists()
            ):
                self.add_error(
                    "guest_email",
                    "This email is already registered. Please log in to book.",
                )

            if not guest_phone:
                self.add_error("guest_phone_number", "Phone Number is required.")

        return cleaned_data
