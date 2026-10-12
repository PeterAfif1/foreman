from datetime import date

from foreman.rules import apply_rules, check_deadline, check_name
from foreman.schema import Lead

RECEIVED = date(2026, 10, 12)


def lead(**kw):
    return Lead(is_lead=True, **kw)


def test_name_only_in_email_becomes_hint():
    text = "need a quote for a roof. jenny.park.la@gmail.com"
    out = check_name(lead(customer_name="jenny"), text)
    assert out.customer_name is None
    assert out.name_hint == "Jenny"


def test_existing_hint_is_kept_when_name_moves():
    text = "quote please, carlos.reyes88@gmail.com"
    out = check_name(lead(customer_name="carlos", name_hint="Carlos Reyes"), text)
    assert (out.customer_name, out.name_hint) == (None, "Carlos Reyes")


def test_name_written_in_message_is_kept():
    text = "Hi this is Sam, redo our bathroom. samantha.ortiz@outlook.com"
    out = check_name(lead(customer_name="Sam", name_hint="Samantha Ortiz"), text)
    assert out.customer_name == "Sam"


def test_signed_full_name_is_kept():
    text = "tiles cracked. Mark Ellison, mellison@gmail.com"
    assert check_name(lead(customer_name="Mark Ellison"), text).customer_name == "Mark Ellison"


def test_deadline_within_60_days_is_soon():
    out = check_deadline(lead(deadline="2026-11-26"), RECEIVED)
    assert out.urgency == "soon"


def test_far_deadline_clears_soon():
    out = check_deadline(lead(deadline="2027-06-01", urgency="soon"), RECEIVED)
    assert out.urgency is None


def test_past_deadline_is_not_soon():
    out = check_deadline(lead(deadline="2026-06-01", urgency="soon"), RECEIVED)
    assert out.urgency is None


def test_emergency_and_flexible_are_left_alone():
    assert (
        check_deadline(lead(deadline="2027-06-01", urgency="emergency"), RECEIVED).urgency
        == "emergency"
    )
    assert (
        check_deadline(lead(deadline="2026-10-20", urgency="flexible"), RECEIVED).urgency
        == "flexible"
    )


def test_bad_deadline_is_dropped():
    out = check_deadline(lead(deadline="next june", urgency="soon"), RECEIVED)
    assert out.deadline is None
    assert out.urgency == "soon"


def test_no_received_date_changes_nothing():
    original = lead(deadline="2027-06-01", urgency="soon")
    assert check_deadline(original, None) == original


def test_non_leads_are_untouched():
    spam = Lead(is_lead=False)
    assert apply_rules(spam, "buy SEO", RECEIVED) == spam
