"""The code gates: clear matches remove a job, everyday wording does not."""

from engine.jobs.gates import run_gates


def gates(
    *,
    company: str = "Acme",
    title: str = "Flutter Engineer",
    location: str | None = None,
    description: str = "Build mobile apps with a friendly team.",
    do_not_apply: list[str] | None = None,
    work_modes: list[str] | None = None,
    eligibility: str | None = None,
    locations: list[str] | None = None,
) -> str | None:
    removal = run_gates(
        company=company,
        title=title,
        location=location,
        description=description,
        do_not_apply=do_not_apply or [],
        work_modes=work_modes or [],
        eligibility=eligibility,
        locations=locations or [],
    )
    return removal.code if removal else None


def test_a_job_with_no_rules_in_the_way_passes() -> None:
    assert gates() is None


def test_do_not_apply_matches_the_company_name_only() -> None:
    assert gates(company="Acme", do_not_apply=["acme"]) == "do_not_apply"
    assert gates(company="ACME, Inc.", do_not_apply=["Acme Ltd"]) == "do_not_apply"
    assert gates(company="Acme Labs", do_not_apply=["Acme"]) is None
    assert gates(company="Acmeville", do_not_apply=["Acme"]) is None
    assert gates(company="Acme", do_not_apply=[]) is None


def test_the_reason_names_the_company() -> None:
    removal = run_gates(
        company="Acme",
        title="t",
        location=None,
        description="d",
        do_not_apply=["Acme"],
        work_modes=[],
        eligibility=None,
        locations=[],
    )
    assert removal is not None
    assert "Acme" in removal.reason


def test_a_clearly_remote_job_is_removed_for_an_onsite_only_track() -> None:
    assert (
        gates(description="This is a fully remote role.", work_modes=["onsite"])
        == "work_mode"
    )
    assert (
        gates(location="Remote, EMEA", work_modes=["onsite", "hybrid"]) == "work_mode"
    )


def test_a_clearly_onsite_job_is_removed_for_a_remote_only_track() -> None:
    assert (
        gates(description="This is an on-site role in Berlin.", work_modes=["remote"])
        == "work_mode"
    )
    assert gates(location="On-site, Nairobi", work_modes=["remote"]) == "work_mode"


def test_a_job_in_a_chosen_mode_passes() -> None:
    assert gates(location="Remote", work_modes=["remote", "hybrid"]) is None
    assert gates(location="Hybrid", work_modes=["hybrid"]) is None


def test_everyday_wording_is_not_a_work_mode() -> None:
    for text in (
        "Join our remote team events and offsites.",
        "You will build hybrid apps and hybrid cloud tools.",
        "On-site interviews are held in the final round.",
        "Remote work is possible for some people.",
    ):
        assert gates(description=text, work_modes=["onsite"]) is None, text


def test_mixed_work_mode_wording_passes() -> None:
    assert (
        gates(
            location="Remote",
            description="This is a hybrid role.",
            work_modes=["onsite"],
        )
        is None
    )


def test_a_negated_work_mode_phrase_is_not_a_work_mode() -> None:
    for text in (
        "This role is not fully remote.",
        "We are no longer a fully remote company.",
        "This is not an on-site role.",
    ):
        assert gates(description=text, work_modes=["hybrid"]) is None, text


def test_company_style_wording_is_not_a_work_mode() -> None:
    assert (
        gates(description="We build hybrid work apps.", work_modes=["remote"]) is None
    )
    assert gates(description="A remote-first company.", work_modes=["onsite"]) is None


def test_no_chosen_work_modes_means_no_rule() -> None:
    assert gates(description="This is a fully remote role.", work_modes=[]) is None


def test_a_region_only_posting_is_removed_when_the_track_does_not_mention_it() -> None:
    assert gates(description="US only. Apply today.", eligibility="Kenya") == (
        "region_only"
    )
    assert gates(
        description="You must reside in the United States.",
        eligibility="Kenya resident",
        locations=["Nairobi"],
    ) == ("region_only")
    assert gates(description="EU residents only.", eligibility="Kenya") == (
        "region_only"
    )
    assert (
        gates(description="Open to UK candidates only.", eligibility="Kenya")
        == "region_only"
    )
    assert (
        gates(location="Canada only", description="x", eligibility="Kenya")
        == "region_only"
    )


def test_a_region_only_posting_passes_when_the_track_mentions_the_region() -> None:
    assert gates(description="US only.", eligibility="Can work in the US") is None
    assert (
        gates(description="EU residents only.", eligibility="x", locations=["Europe"])
        is None
    )
    assert gates(description="Canada only", eligibility="Canadian citizen") is None


def test_a_negated_or_listed_region_phrase_is_not_a_restriction() -> None:
    for text in (
        "This role is not US only.",
        "There is no EU only restriction.",
        "You must be located in the US or Canada.",
        "You must be located in Canada, the US or the UK.",
        "Open to US or Canada only.",
    ):
        assert gates(description=text, eligibility="Kenya resident") is None, text


def test_a_listed_region_is_still_removed_when_the_track_names_none_of_them() -> None:
    # The two forms the reviewer said must keep working next to the lists above.
    assert gates(description="US only.", eligibility="Kenya resident") == "region_only"
    assert (
        gates(description="Canada only", eligibility="Kenya resident") == "region_only"
    )


def test_without_eligibility_notes_a_region_posting_passes_on() -> None:
    # A place name does not say which country it is in, so there is nothing to compare.
    assert gates(description="US only.") is None
    assert gates(description="US only.", locations=["New York"]) is None
    assert gates(description="US only.", eligibility="   ") is None


def test_everyday_wording_is_not_a_region_restriction() -> None:
    for text in (
        "Contact us only by email, never by phone.",
        "Work with us only if you love mobile.",
        "We focus on customers across the world.",
        "Our customers include US and EU banks.",
        "We hire worldwide.",
    ):
        assert gates(description=text, eligibility="Kenya") is None, text


def test_the_first_matching_rule_wins() -> None:
    removal = run_gates(
        company="Acme",
        title="t",
        location="Remote",
        description="US only.",
        do_not_apply=["Acme"],
        work_modes=["onsite"],
        eligibility=None,
        locations=[],
    )
    assert removal is not None
    assert removal.code == "do_not_apply"


def test_a_negated_or_limited_location_is_not_a_work_mode() -> None:
    assert gates(location="Nairobi (not remote)", work_modes=["onsite"]) is None
    assert gates(location="Not on-site", work_modes=["remote"]) is None


def test_a_work_mode_that_is_taken_back_or_limited_is_not_clear() -> None:
    for text in (
        "Fully remote is not an option here.",
        "Fully remote isn't possible for this role.",
        "Remote only during onboarding, then on-site role.",
        "Fully remote until the new office opens.",
    ):
        assert gates(description=text, work_modes=["onsite"]) is None, text


def test_a_region_turned_inside_out_is_not_a_restriction() -> None:
    for text in (
        "Candidates outside the US only.",
        "Applicants excluding the EU only.",
        "Open to non-US candidates only.",
        "Residents other than the UK only.",
    ):
        assert gates(description=text, eligibility="Kenya resident") is None, text


def test_the_clear_cases_still_remove_after_the_repairs() -> None:
    assert gates(location="Remote", work_modes=["onsite"]) == "work_mode"
    assert gates(location="On-site", work_modes=["remote"]) == "work_mode"
    assert (
        gates(description="This is a fully remote role.", work_modes=["onsite"])
        == "work_mode"
    )
    assert gates(description="US only.", eligibility="Kenya") == "region_only"
    assert (
        gates(description="You must reside in the United States.", eligibility="Kenya")
        == "region_only"
    )


def test_a_long_hostile_posting_is_checked_quickly() -> None:
    import time

    unit = "Candidates outside the US only. Not remote. Fully remote is not an option. "
    text = unit * (200_000 // len(unit))
    started = time.perf_counter()
    gates(description=text, work_modes=["onsite"], eligibility="Kenya")
    gates(location="Not remote " * 20_000, work_modes=["onsite"], eligibility="Kenya")
    assert time.perf_counter() - started < 1.0


def test_a_location_that_offers_choices_is_not_one_clear_mode() -> None:
    for location in (
        "Nairobi or Remote",
        "Remote / Hybrid",
        "On-site & remote",
        "Remote or on-site",
        "Hybrid and remote",
    ):
        assert gates(location=location, work_modes=["onsite"]) is None, location
        assert gates(location=location, work_modes=["remote"]) is None, location


def test_a_plain_location_still_states_its_mode() -> None:
    assert gates(location="Remote, EMEA", work_modes=["onsite"]) == "work_mode"
    assert gates(location="On-site", work_modes=["remote"]) == "work_mode"
    assert gates(location="Hybrid", work_modes=["remote"]) == "work_mode"
    # An "or" in a place name that names no mode changes nothing.
    assert gates(location="Nairobi or Mombasa", work_modes=["remote"]) is None


def test_a_location_with_a_denial_is_not_one_clear_mode() -> None:
    for location in (
        "Nairobi (Remote work not allowed)",
        "Nairobi - no remote work",
        "Remote working isn't possible, Nairobi",
        "On-site only, never remote",
    ):
        assert gates(location=location, work_modes=["onsite"]) is None, location
        assert gates(location=location, work_modes=["remote"]) is None, location


def test_a_plain_location_with_other_words_still_states_its_mode() -> None:
    assert gates(location="Nairobi, Kenya (Remote)", work_modes=["onsite"]) == (
        "work_mode"
    )
    assert gates(location="On-site, Nairobi", work_modes=["remote"]) == "work_mode"


def test_is_negated_reads_the_words_just_before_a_position() -> None:
    from engine.jobs.gates import is_negated

    text = "This is not required here"
    assert is_negated(text, text.index("required"))
    assert not is_negated("This is required here", 8)
    assert not is_negated("Required", 0)
    assert is_negated("It isn't required", 17 - len("required"))


def test_is_negated_only_looks_inside_the_same_line_or_sentence() -> None:
    from engine.jobs.gates import is_negated

    text = "No degree needed\nNice to have"
    assert not is_negated(text, text.index("Nice"))
    text = "Not for all. Required"
    assert not is_negated(text, text.index("Required"))
    text = "Not a plus"
    assert is_negated(text, text.index("plus") - 2)
