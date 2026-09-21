from app.handlers.support_ticket_replied import build_support_ticket_replied_pushes
from app.messaging.events import SupportTicketRepliedEvent

CREATOR = "11111111-1111-1111-1111-111111111111"


def _event(**overrides) -> SupportTicketRepliedEvent:
    base = dict(
        event_id="evt-1",
        event_type="support.ticket_replied",
        ticket_id="ticket-1",
        booking_id="book-1",
        ticket_subject="No me devolvieron el pago",
        recipient_user_id=CREATOR,
        body="Ya procesamos tu reembolso, debería verse en 48hs",
    )
    base.update(overrides)
    return SupportTicketRepliedEvent(**base)


def test_notifies_the_ticket_creator_with_a_preview():
    pushes = build_support_ticket_replied_pushes(_event())

    assert [p.user_id for p in pushes] == [CREATOR]
    assert "No me devolvieron el pago" in pushes[0].title
    assert pushes[0].body == "Ya procesamos tu reembolso, debería verse en 48hs"
    assert pushes[0].data == {"type": "support.ticket_replied", "ticketId": "ticket-1", "bookingId": "book-1"}


def test_long_reply_is_truncated_with_ellipsis():
    long_body = "a" * 200
    pushes = build_support_ticket_replied_pushes(_event(body=long_body))

    assert len(pushes[0].body) == 120
    assert pushes[0].body.endswith("…")


def test_empty_when_no_recipient():
    assert build_support_ticket_replied_pushes(_event(recipient_user_id="")) == []


def test_falls_back_to_generic_title_when_subject_missing():
    pushes = build_support_ticket_replied_pushes(_event(ticket_subject=""))

    assert pushes[0].title == "🎧 Soporte respondió tu ticket"
