import datetime

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import Service, ServiceProvider, WorkingHours


class ServiceProviderForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = ["business_name", "description", "business_address", "business_logo"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Describe your specific services and what sets you apart...",
                }
            ),
            "business_address": forms.TextInput(
                attrs={"placeholder": "e.g. 123 Main St, New York"}
            ),
            "business_logo": forms.FileInput(
                attrs={"id": "id_business_logo", "accept": "image/*"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["description"].required = True
        self.fields["business_address"].required = True

        if not self.instance.pk or not self.instance.business_logo:
            self.fields["business_logo"].required = True
            self.fields["business_logo"].widget.attrs.update({"required": "required"})


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["title", "description", "price", "duration", "image", "is_active"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "description": forms.Textarea(attrs={"rows": 3}),
            "price": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "duration": forms.NumberInput(attrs={"min": "15", "step": "15"}),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input mt-0",
                    "style": "width: 25px; height: 25px;",
                }
            ),
            "image": forms.FileInput(
                attrs={"class": "d-none", "id": "imageUpload", "accept": "image/*"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.provider = kwargs.pop("provider", None)
        super().__init__(*args, **kwargs)

        # Enforce image requirement strictly on creation, gracefully ignore on update if present
        if not self.instance.pk or not self.instance.image:
            self.fields["image"].required = True
            self.fields["image"].widget.attrs.update({"required": "required"})

    def clean(self):
        cleaned_data = super().clean()
        duration = cleaned_data.get("duration")
        price = cleaned_data.get("price")
        provider = getattr(self, "provider", None) or getattr(
            self.instance, "provider", None
        )

        if duration is not None:
            if duration <= 0:
                self.add_error("duration", "Service duration must be greater than 0.")
            elif duration % 15 != 0:
                self.add_error(
                    "duration", "Service duration must be in 15-minute intervals."
                )

        if price is not None and price <= 0:
            self.add_error("price", "Service price must be greater than 0.")

            # if duration > 480:
            #     self.add_error('duration', 'Service duration mathematically cannot exceed 8 hours (480 minutes) per the platform limitations.')

            if provider:
                working_hours = WorkingHours.objects.filter(
                    provider=provider, is_working_day=True
                )

                max_shift_minutes = 0
                for wh in working_hours:
                    if wh.start_time and wh.end_time:
                        d1 = datetime.datetime.combine(
                            timezone.now().date(), wh.start_time
                        )
                        d2 = datetime.datetime.combine(
                            timezone.now().date(), wh.end_time
                        )
                        shift_length = (d2 - d1).total_seconds() / 60
                        max_shift_minutes = max(max_shift_minutes, shift_length)

                if max_shift_minutes > 0 and duration > max_shift_minutes:
                    self.add_error(
                        "duration",
                        f"Service duration technically exceeds your longest active daily shift ({int(max_shift_minutes)} minutes). Consider making your active schedule longer on the Working Hours page first.",
                    )

        return cleaned_data


class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ["day_of_week", "start_time", "end_time", "is_working_day"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "start_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "end_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "day_of_week": forms.HiddenInput(),
            "is_working_day": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input mt-0",
                    "style": "width: 20px; height: 20px;",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_working_day = cleaned_data.get("is_working_day")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if is_working_day:
            if not start_time:
                self.add_error("start_time", "Start time is required.")
            if not end_time:
                self.add_error("end_time", "End time is required.")
            if start_time and end_time and start_time >= end_time:
                self.add_error("end_time", "End time must be after start time...")

        return cleaned_data


WorkingHoursFormSet = inlineformset_factory(
    ServiceProvider,
    WorkingHours,
    form=WorkingHoursForm,
    extra=0,
    can_delete=False,
    max_num=7,
)
