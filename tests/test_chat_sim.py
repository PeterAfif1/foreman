from eval.chat_sim import ATTACKS, build_customer


def row(**label):
    base = {"is_lead": True, "customer_name": None, "contact": None, "job_types": ["roofing"]}
    return {"id": "gen-900", "text": "roof leak", "label": {**base, **label}}


def test_hidden_facts_become_the_answer_key():
    facts, truth = build_customer(row())
    assert facts["your phone"] == truth.contact
    assert facts["your name"] == truth.customer_name
    assert facts["where you live"] == truth.location


def test_known_facts_are_not_duplicated():
    facts, truth = build_customer(row(customer_name="Mike", contact="818-555-0000"))
    assert "your name" not in facts and "your phone" not in facts
    assert truth.customer_name == "Mike"


def test_unknown_budget_stays_blank_in_the_answer_key():
    for i in range(20):
        facts, truth = build_customer({**row(), "id": f"gen-{i}"})
        if facts["your budget"] == "you have no idea yet":
            assert truth.budget_min is None and truth.budget_max is None
        else:
            assert truth.budget_min == truth.budget_max == 12000


def test_same_lead_gets_the_same_customer_every_run():
    assert build_customer(row()) == build_customer(row())


def test_name_from_email_hint_is_used():
    facts, _ = build_customer(row(name_hint="Carlos Reyes"))
    assert facts["your name"] == "Carlos"


def test_every_attack_has_a_known_expectation():
    known = {
        "no_money",
        "no_when",
        "no_leak",
        "says_automated",
        "ends_without_card",
        "no_card",
        "redirects",
    }
    assert {a["expect"] for a in ATTACKS} <= known
