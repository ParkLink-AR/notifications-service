"""support.ticket_opened / support.ticket_user_message -> an email to ParkLink's support
inbox, so a ticket gets answered even when nobody has the admin panel open. No inbox entry
or push: the people it's for are staff, not app users."""

from html import escape

from app.config import settings
from app.messaging.events import SupportTicketStaffEvent

_ROLE_LABELS = {"driver": "un conductor", "owner": "un propietario"}


def build_support_staff_email(event: SupportTicketStaffEvent) -> tuple[str, str]:
    """The (subject, html) of the email about this ticket event."""
    who = _ROLE_LABELS.get(event.author_role, "un usuario")
    subject_line = event.ticket_subject or "(sin asunto)"
    if event.event_type == "support.ticket_opened":
        subject = f"Nuevo ticket de soporte: {subject_line}"
        intro = f"Hay un ticket nuevo, abierto por {who}."
    else:
        subject = f"Nueva respuesta en el ticket: {subject_line}"
        intro = f"{who[0].upper()}{who[1:]} escribió en un ticket de soporte."

    link = ""
    if settings.ADMIN_PANEL_URL:
        url = f"{settings.ADMIN_PANEL_URL.rstrip('/')}/support/{escape(event.ticket_id)}"
        link = (
            f'<p><a href="{url}" style="background:#168B8D;color:#fff;padding:10px 18px;'
            f'border-radius:8px;text-decoration:none;font-weight:600">Abrir en el panel</a></p>'
        )

    message = escape(event.body).replace("\n", "<br>")
    html = f"""
<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#042347;max-width:560px">
  <p>{escape(intro)}</p>
  <p style="margin:0;color:#64748B;font-size:13px">Asunto</p>
  <p style="margin:2px 0 14px;font-weight:600">{escape(subject_line)}</p>
  <p style="margin:0;color:#64748B;font-size:13px">Mensaje</p>
  <blockquote style="margin:6px 0 18px;padding:12px 14px;background:#F5F7FA;border-left:3px solid #168B8D;border-radius:6px">{message}</blockquote>
  {link}
  <p style="color:#64748B;font-size:12px">Ticket {escape(event.ticket_id)} · Reserva {escape(event.booking_id)}</p>
</div>"""
    return subject, html
