"""Tests for employment years computation from resume text."""

from datetime import date

from apps.resumes.resume_content import (
    compute_years_of_experience,
    format_years_of_experience_constraint,
)

REFERENCE = date(2026, 6, 1)


class TestComputeYearsOfExperience:
    def test_single_role_with_present(self):
        resume = """
        WORK EXPERIENCE
        Software Engineer --- Acme Corp
        Jan 2022 -- Present
        - Built APIs

        EDUCATION
        B.S. Computer Science --- State University
        2018 -- 2022
        """
        assert compute_years_of_experience(resume, reference_date=REFERENCE) == 4

    def test_year_only_ranges(self):
        resume = """
        EXPERIENCE
        Engineer --- Beta Inc
        2022 -- Present
        """
        assert compute_years_of_experience(resume, reference_date=REFERENCE) == 4

    def test_merges_overlapping_roles(self):
        resume = """
        PROFESSIONAL EXPERIENCE
        Analyst --- First Co | Jan 2020 -- Dec 2021
        Engineer --- Second Co | Jun 2021 -- Present
        """
        assert compute_years_of_experience(resume, reference_date=REFERENCE) == 6

    def test_excludes_education_section_dates(self):
        resume = """
        EXPERIENCE
        Developer --- Startup
        Mar 2021 -- Present

        EDUCATION
        B.S. CS --- University
        2014 -- 2018
        """
        assert compute_years_of_experience(resume, reference_date=REFERENCE) == 5

    def test_returns_none_without_parseable_dates(self):
        resume = "Jane Doe\nSenior Python Engineer with Django experience."
        assert compute_years_of_experience(resume, reference_date=REFERENCE) is None


class TestFormatYearsOfExperienceConstraint:
    def test_includes_computed_years(self):
        text = format_years_of_experience_constraint(4, reference_date=REFERENCE)
        assert "4 years total" in text
        assert "MUST NOT claim more than 4 years" in text

    def test_omits_guess_when_unknown(self):
        text = format_years_of_experience_constraint(None)
        assert "Do NOT state a specific year count" in text
