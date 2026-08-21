import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags


def send_booking_email(appointment, action="booked", request=None):
    """
    Sends customized conversational HTML emails for Bookings to BOTH the Client and the Provider.
    action mapping expects: 'booked', 'confirmed', 'cancelled', 'rescheduled'
    """
    if appointment.customer_user:
        client_name = str(appointment.customer_user.email).split("@")[0].capitalize()
    else:
        client_name = appointment.guest_name

    client_email = (
        appointment.customer_user.email
        if appointment.customer_user
        else appointment.guest_email
    )
    provider = appointment.provider
    provider_name = provider.business_name
    provider_email = provider.user.email

    date_str = appointment.date.strftime("%B %d, %Y")
    time_str = f"{appointment.start_time.strftime('%I:%M %p')} - {appointment.end_time.strftime('%I:%M %p')}"
    ref = appointment.booking_reference
    total_price = appointment.total_price

    # Define dynamic strings based on recipient
    client_action_strings = {
        "booked": f"Your appointment request has been successfully received and is securely pending confirmation from {provider_name}.",
        "confirmed": f"Great news! Your upcoming appointment has been successfully CONFIRMED by {provider_name}.",
        "cancelled": f"Your appointment with {provider_name} has been CANCELLED.",
        "rescheduled": f"Your appointment with {provider_name} has been successfully RESCHEDULED to your newly requested time.",
    }

    provider_action_strings = {
        "booked": f"A new appointment request was just created by {client_name}. It is awaiting your CONFIRMATION in your dashboard.",
        "confirmed": f"You have successfully confirmed the appointment for {client_name}.",
        "cancelled": f"An appointment scheduled by {client_name} has been CANCELLED.",
        "rescheduled": f"{client_name} has successfully RESCHEDULED their appointment. Please review the new time.",
    }

    client_body = client_action_strings.get(
        action, "There was an update to your appointment."
    )
    provider_body = provider_action_strings.get(
        action, "There was an update to an appointment."
    )

    manage_url = None
    if request:
        try:
            if appointment.customer_user:
                manage_url = request.build_absolute_uri(
                    reverse("customer_appointments")
                )
            else:
                manage_url = request.build_absolute_uri(
                    reverse(
                        "guest_manage_appointment", args=[appointment.booking_reference]
                    )
                )
        except Exception:  # noqa: BLE001, S110
            pass

    context = {
        "client_name": client_name,
        "client_email": client_email,
        "provider_name": provider_name,
        "date": date_str,
        "time": time_str,
        "total_price": total_price,
        "ref": ref,
        "manage_url": manage_url,
    }

    # 1. Send Email to Client
    if client_email:
        client_context = {**context, "body_status": client_body}
        client_html = render_to_string(
            "emails/client_notification.html", client_context
        )
        client_msg = EmailMultiAlternatives(
            subject=f"BookWise Appointment: {action.title()} with {provider_name}",
            body=strip_tags(client_html),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bookwise.com"),
            to=[client_email],
        )
        client_msg.attach_alternative(client_html, "text/html")

        # Ensure fast non-blocking HTTP responses while routing SMTP payloads
        threading.Thread(target=client_msg.send, kwargs={"fail_silently": True}).start()

    # 2. Send Email to Provider
    if provider_email:
        provider_context = {**context, "body_status": provider_body}
        provider_html = render_to_string(
            "emails/provider_notification.html", provider_context
        )
        provider_msg = EmailMultiAlternatives(
            subject=f"Action/Update: Appointment {action.title()} by {client_name}",
            body=strip_tags(provider_html),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@bookwise.com"),
            to=[provider_email],
        )
        provider_msg.attach_alternative(provider_html, "text/html")
        threading.Thread(
            target=provider_msg.send, kwargs={"fail_silently": True}
        ).start()
