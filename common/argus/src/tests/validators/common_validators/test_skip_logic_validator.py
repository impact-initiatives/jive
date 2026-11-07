import polars as pl
import pytest

from argus.models.base import SchemaColumnMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.base import ValidationResult
from argus.validators.common_validators import (
    SkipLogicCheck,
)
from argus.validators.helpers.skip_logic_parser import build_relevance_expression
from tests.helpers import (
    build_excel_data,
    build_schema_with_process,
    do_basic_checks,
    error_counter,
)


def get_validator(schema: BaseDatasetSchema, parent_sheet: str, child_sheets: list[str] | None):
    """Create a UniqueColumn validator instance"""
    return SkipLogicCheck(schema=schema, parent_sheet=parent_sheet, child_sheets=child_sheets)


def run_skip_validation(
    columns: dict[str, list[tuple[str, list]]],
) -> list[ValidationResult]:
    """Build schema + data, run the validator on 'clean_data', return result."""
    schema = build_schema_with_process(
        {
            "clean_data": ["uuid"],
            "survey": ["relevant", "name"],
            "child_data": ["person_id"],
        },
        process_details={},
        process_sheet="",
        process_column="",
    )
    schema.add_column_to_sheet("child_data", SchemaColumnMap(standard_name="uuid"))
    child_sheet = schema.get_schema_loaded_sheet("child_data")
    assert child_sheet is not None
    child_sheet.parent_linking_column = "uuid"
    child_sheet.parent_sheet = "clean_data"

    data = build_excel_data(columns)
    validator = get_validator(
        schema,
        parent_sheet="clean_data",
        child_sheets=["child_data"] if "child_data" in columns else None,
    )
    return validator.validate(data)


class TestParserLiterals:
    """Literals: strings, numbers, booleans, quoting styles."""

    def test_string_equality_true(self):
        # condition TRUE, value missing -> 1 violation (shown but empty)
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_string_equality_true_not_required(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["no"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_string_equality_child_true(self):
        # one missing value. one has value but shouldnt
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "child_data": [
                    ("uuid", [1, 3]),
                    ("person_id", [6, 7]),
                    ("child_gender", ["bla", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["child_gender"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        filterd_results = error_counter(result)
        assert filterd_results[0].details is not None
        assert len(filterd_results[0].details["uuid"]) == 2

    def test_string_equality_false_shows_no_violation(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("gender", ["male", "female"]),
                    ("gender_other", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_double_quoted_string(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("gender", ["other", "male"]),
                    ("gender_other", ["", ""]),
                ],
                "survey": [
                    ("relevant", ['${gender}="other"']),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_case_sensitive_string_equality(self):
        # 'Other' != 'other' -- the condition is false, so empty value is fine
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("gender", ["Other"]),
                    ("gender_other", [""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_true_function_always_shown(self):
        # true() is always relevant -> an empty question must be flagged
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("some_flag", ["1", "2"]),
                    ("always_probe", ["", ""]),  # empty target question
                ],
                "survey": [
                    ("relevant", ["true() or ${some_flag}='2'"]),
                    ("name", ["always_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2

    def test_false_function_never_shown(self):
        # false() is never relevant -> any value present is a violation
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("some_flag", ["1", "2"]),
                    ("never_probe", ["", "ghost"]),  # record 2: hidden but filled
                ],
                "survey": [
                    ("relevant", ["false() and ${some_flag}='2'"]),
                    ("name", ["never_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_bare_true_keyword(self):
        # If your parser also supports bare 'true' (not the function form),
        # pin that too:
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("some_flag", ["1"]),
                    ("always_note", [""]),
                ],
                "survey": [
                    ("relevant", ["true"]),
                    ("name", ["always_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_false_makes_condition_false(self):
        # false() or <anything> is always False -> question always hidden ->
        # an empty target is consistent, a filled target is a violation
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("some_flag", ["1", "2"]),  # real column, never actually consulted
                    ("always_note", ["", "filled"]),
                ],
                "survey": [
                    ("relevant", ["false() or ${some_flag}='x'"]),
                    ("name", ["always_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # rec 1: hidden & empty -> ok
        # rec 2: hidden & filled -> "value when question was skipped"
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserComparisonOperators:
    """=, !=, >, <, >=, <= against numeric literals."""

    @pytest.mark.parametrize(
        "relevant,expect_violations",
        [
            ("${age} = 15", 1),
            ("${age} != 15", 2),
            ("${age} > 17", 1),
            ("${age} < 17", 2),
            ("${age} >= 18", 1),
            ("${age} <= 15", 2),
        ],
    )
    def test_numeric_comparisons(self, relevant, expect_violations):
        # ages: 10, 15, 20 ; age_other always empty (shown whenever relevant)
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("age", [10, 15, 20]),
                    ("age_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", [relevant]),
                    ("name", ["age_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == expect_violations

    def test_negative_numeric_literal(self):
        # sentinel value: -999 means 'not applicable'
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("income", [500, -999, 0]),
                    ("income_source", ["salary", "salary", "farm"]),
                ],
                "survey": [
                    ("relevant", ["${income} != -999"]),
                    ("name", ["income_source"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # record 1: -999 -> hidden but answered 'salary' -> violation
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_numeric_literal_left_side(self):
        # reversed operand order must also cast correctly
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("age", [10, 20]),
                    ("minor_guardian", ["", "present"]),
                ],
                "survey": [
                    ("relevant", ["15 > ${age}"]),
                    ("name", ["minor_guardian"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2


class TestParserBooleanLogic:
    """and / or / not, parentheses, precedence."""

    def test_and_both_true(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4]),
                    ("gender", ["female", "female", "male", "male"]),
                    ("age", [20, 10, 20, 10]),
                    ("pregnant", ["", "", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender} = 'female' and ${age} >= 15"]),
                    ("name", ["pregnant"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # only record 1 satisfies the condition
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_or_short_circuit_either_side(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("resp_hoh_yn", ["yes", "no"]),
                    ("non_hoh_consent", ["no", "no"]),
                    ("second_consented", ["", ""]),
                ],
                "survey": [
                    (
                        "relevant",
                        ["selected(${resp_hoh_yn}, 'yes') or selected(${non_hoh_consent},'yes')"],
                    ),
                    ("name", ["second_consented"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # record 1 satisfied via first disjunct -> 1 violation
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_not_operator(self):
        # ODK semantics: not(comparison over unanswered ref) is TRUE,
        # because the inner comparison is FALSE, not null.
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("dis_reasons_primary", [""]),  # unanswered
                    ("dis_probe", [""]),
                ],
                "survey": [
                    ("relevant", ["not(${dis_reasons_primary} != 'yes_entirely')"]),
                    ("name", ["dis_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # inner: '' != 'x' -> null -> fill_false; not(false) -> true -> shown but empty
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_parentheses_override_precedence(self):
        # and binds tighter than or:  a='x' or b='y' and c='z'
        # means a='x' or (b='y' and c='z')  -- parens flip the grouping
        base_cols = [
            ("uuid", [1, 2]),
            ("a", ["x", "no"]),
            ("b", ["no", "yes"]),
            ("c", ["no", "yes"]),
            ("target", ["", ""]),
        ]
        result = run_skip_validation(
            {
                "clean_data": base_cols,
                "survey": [
                    ("relevant", ["(${a}='x' or ${b}='y') and ${c}='no'"]),
                    ("name", ["c"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # ('x' or 'yes') and 'no' -> only record 1
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_nested_parentheses(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("dis_forced", ["yes_but_back"]),
                    ("dis_area_origin", ["same_neighbourhood"]),
                    ("ds_plans", ["move_back_original"]),
                    ("nested_target", [""]),
                ],
                "survey": [
                    (
                        "relevant",
                        [
                            "${dis_forced}='yes_but_back' and (${dis_area_origin}="
                            + "'same_neighbourhood' and ${ds_plans}='move_back_original')"
                        ],
                    ),
                    ("name", ["nested_target"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_whitespace_insensitivity(self):
        # spaces, tabs, no-space variants must all parse identically
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("consent_hh", ["no"]),
                    ("refusal_notes", [""]),
                ],
                "survey": [
                    ("relevant", ["${consent_hh}='no'"]),
                    ("name", ["refusal_notes"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        # and the cramped version:
        result2 = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("consent_hh", ["no"]),
                    ("refusal_notes", [""]),
                ],
                "survey": [
                    ("relevant", ["${consent_hh}='no'"]),
                    ("name", ["refusal_notes"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result2, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserArithmetic:
    """+, -, *, div, mod — including string-typed columns (the cast path)."""

    def test_arith_column_times_literal(self):
        # ${expenditure} > ${income} * 3  -> both sides must self-cast
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("expenditure", ["400", "50"]),  # string-typed export
                    ("income", ["100", "50"]),
                    ("overspend_probe", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["${expenditure} > ${income} * 3"]),
                    ("name", ["overspend_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # only record 1: 400 > 300
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_addition(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("hh_size", ["5", "2"]),
                    ("extra_members", ["1", "0"]),
                    ("large_hh_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["${hh_size} + ${extra_members} > 5"]),
                    ("name", ["large_hh_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # fix column names to match: (use hh_size/extra consistently)
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_modulo(self):
        # count-selected-like arithmetic: ${n} mod 2 = 0
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("n", ["4", "3"]),
                    ("even_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["${n} mod 2 = 0"]),
                    ("name", ["even_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_div(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("total", ["10", "7"]),
                    ("parts", ["2", "2"]),
                    ("ratio_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["${total} div ${parts} = 5"]),
                    ("name", ["ratio_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_negative_sentinel_comparison(self):
        # regression test for the unary-minus parsing bug: -999 must
        # reach the comparison as a numeric literal, forcing the f64 cast
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("income", ["500", "-999", "200"]),
                    ("income_note", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${income} != -999"]),
                    ("name", ["income_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # all records: shown & filled -> consistent
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2

    def test_neg_ref_compared_to_negative_literal(self):
        # ${loss} = '50' -> -(50) = -50 < -10 -> shown; empty target -> violation
        # ${loss} = '5'  -> -5 < -10 is False -> hidden; consistent
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("loss", ["50", "5"]),  # string-typed export
                    ("loss_probe", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["-${loss} < -10"]),
                    ("name", ["loss_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_neg_of_parenthesised_arithmetic(self):
        # -(3 + 4) = -7 is a constant True -> always shown; empty -> 2 violations
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("always_probe", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["-(3 + 4) = -7"]),
                    ("name", ["always_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2

    def test_neg_on_unanswered_ref_is_false(self):
        # ODK: -(unanswered) is null; comparison against null is False
        # -> question hidden; empty target is consistent
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("loss", [""]),  # unanswered
                    ("loss_probe", [""]),
                ],
                "survey": [
                    ("relevant", ["-${loss} < -10"]),
                    ("name", ["loss_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_double_negation_of_literal_does_not_crash(self):
        # '--5' is a valid ODK expression; naive literal folding produces
        # the string '--5', which float() cannot parse. Verify it either
        # folds to 5 or raises ValueError -- a crash from float() parsing
        # would ALSO satisfy this, but see the fix below.
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("always_probe", [""]),
                ],
                "survey": [
                    ("relevant", ["--5 = 5"]),
                    ("name", ["always_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # -(-5) = 5 -> True -> shown but empty
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserSelectedFunction:
    def test_select_one_match(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("resp_hoh_yn", ["yes", "no"]),
                    ("hoh_consent", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["selected(${resp_hoh_yn}, 'yes')"]),
                    ("name", ["hoh_consent"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_select_multiple_space_separated(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("reasons", ["food water", "shelter", ""]),
                    ("reason_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["selected(${reasons}, 'water')"]),
                    ("name", ["reason_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # only record 1
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_selected_multiple_words_not_substring(self):
        # 'water' must not match 'rainwater' -- split-on-space, not substring
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("reasons", ["rainwater"]),
                    ("reason_other", ["filled_anyway"]),
                ],
                "survey": [
                    ("relevant", ["selected(${reasons}, 'water')"]),
                    ("name", ["reason_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # hidden but answered
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_count_selected(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("reasons", ["food water", "food", ""]),
                    ("multi_reason_probe", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["count-selected(${reasons}) > 1"]),
                    ("name", ["multi_reason_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # only record 1
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_count_selected_empty_is_zero(self):
        # regression: null/empty must count as 0, not 1 ([''] trap)
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("reasons", ["", "food"]),
                    ("no_reason_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["count-selected(${reasons}) = 0"]),
                    ("name", ["no_reason_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)  # only record 1
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserEmptyValueSemantics:
    """ODK: any comparison against an empty/unanswered ref is FALSE."""

    def test_empty_ref_equals_literal_is_false(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("consent_hh", [""]),  # unanswered
                    ("refusal_reason", [""]),
                ],
                "survey": [
                    ("relevant", ["${consent_hh}='no'"]),
                    ("name", ["refusal_reason"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)  # hidden AND empty -> consistent

    def test_empty_ref_ne_literal_is_false(self):
        # the dangerous case: '' != 'yes_entirely' must be FALSE (not true)
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("dis_reasons_primary", [""]),
                    ("dis_followup", [""]),
                ],
                "survey": [
                    ("relevant", ["${dis_reasons_primary} != 'yes_entirely'"]),
                    ("name", ["dis_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_whitespace_only_ref_counts_as_missing(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("consent_hh", ["   "]),  # whitespace only
                    ("refusal_reason", [""]),
                ],
                "survey": [
                    ("relevant", ["${consent_hh}='no'"]),
                    ("name", ["refusal_reason"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_both_violation_directions(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4]),
                    ("consent_hh", ["no", "yes", "yes", "no"]),
                    ("refusal_reason", ["", "declined", "", ""]),  # one per case
                ],
                "survey": [
                    ("relevant", ["${consent_hh}='no'"]),
                    ("name", ["refusal_reason"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # rec 1: shown & empty -> violation (no value when shown)
        # rec 2: hidden & filled -> violation (value when skipped)
        # rec 3: hidden & empty  -> ok
        # rec 4: shown & filled  -> ok
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 3


class TestParserStartsWithFunction:
    def test_starts_with_match(self):
        # 'piped_tap' starts with 'piped' -> shown & empty -> 1 violation
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("water_source", ["piped_tap", "well"]),
                    ("tap_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'piped')"]),
                    ("name", ["tap_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_starts_with_second_word_no_match(self):
        # prefix anchored at the START only: 'food water' does not
        # start with 'water' even though 'water' appears in the string
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("reasons", ["food water"]),
                    ("water_note", [""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${reasons}, 'water')"]),
                    ("name", ["water_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)  # hidden & empty -> consistent

    def test_starts_with_prefix_inside_word_no_match(self):
        # not a substring match: 'rainwater' does not start with 'water'
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("water_source", ["rainwater"]),
                    ("water_note", [""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'water')"]),
                    ("name", ["water_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_starts_with_exact_value_matches(self):
        # prefix equal to the whole value still matches
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("water_source", ["piped"]),
                    ("piped_note", [""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'piped')"]),
                    ("name", ["piped_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_starts_with_hidden_but_filled(self):
        # other violation direction: 'well' fails the prefix -> hidden,
        # but a value is present anyway
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("water_source", ["well"]),
                    ("tap_note", ["filled_anyway"]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'piped')"]),
                    ("name", ["tap_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_starts_with_empty_ref_is_false(self):
        # unanswered ref -> condition False -> hidden & empty -> consistent
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("water_source", [""]),
                    ("tap_note", [""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'piped')"]),
                    ("name", ["tap_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_starts_with_whitespace_only_ref_is_false(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("water_source", ["   "]),
                    ("tap_note", [""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'piped')"]),
                    ("name", ["tap_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_starts_with_case_insensitive(self):
        # consistent with selected(): matching is case-insensitive.
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("water_source", ["Piped_Tap"]),
                    ("tap_note", [""]),
                ],
                "survey": [
                    ("relevant", ["starts-with(${water_source}, 'piped')"]),
                    ("name", ["tap_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserStringFunctions:
    """ends-with / contains / regex — prefix anchoring and literal matching."""

    def test_ends_with_match(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("hh_id", ["KE_001", "UG_44"]),
                    ("ke_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["ends-with(${hh_id}, '_001')"]),
                    ("name", ["ke_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_ends_with_other_position_no_match(self):
        # 'water_bottle_food' contains 'food' but does not END with it
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("reasons", ["water_food_bottle"]),
                    ("note", [""]),
                ],
                "survey": [
                    ("relevant", ["ends-with(${reasons}, 'food')"]),
                    ("name", ["note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_contains_matches_middle_of_value(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("other_specify", ["irrigation pump", "none"]),
                    ("irrigation_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["contains(${other_specify}, 'pump')"]),
                    ("name", ["irrigation_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_contains_is_literal_not_regex(self):
        # 'price usd' contains the inner text 'usd' but NOT the literal '(usd)'.
        # Under regex semantics, the pattern '(usd)' is a capture group around
        # 'usd' and WOULD match. Only literal=True gives the correct False.
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("comment", ["price usd", "nothing to see"]),
                    ("price_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["contains(${comment}, '(usd)')"]),
                    ("name", ["price_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # literal semantics: neither value matches -> question hidden & empty
        # -> 0 violations. (Regex semantics would flag record 1 as shown-but-empty.)
        do_basic_checks(result, 0)

    def test_contains_literal_parens_positive(self):
        # 'cost (usd) total' DOES contain the literal '(usd)'
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("comment", ["cost (usd) total"]),
                    ("price_note", [""]),
                ],
                "survey": [
                    ("relevant", ["contains(${comment}, '(usd)')"]),
                    ("name", ["price_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_regex_match(self):
        # IDs must match the ^KE_ pattern
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("hh_id", ["KE_001", "UG_44"]),
                    ("ke_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["regex(${hh_id}, '^KE_')"]),
                    ("name", ["ke_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_regex_non_matching_value_hidden(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("hh_id", ["KE_001", "UG_44"]),
                    ("ke_note", ["", "ghost"]),
                ],
                "survey": [
                    ("relevant", ["regex(${hh_id}, '^KE_')"]),
                    ("name", ["ke_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # rec 2: hidden but filled -> 1 violation
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2

    def test_string_length_numeric_comparison(self):
        # open 'other' answers shorter than 3 chars are treated as junk
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("occupation_other", ["x", "carpenter"]),
                    ("clarify_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["string-length(${occupation_other}) < 3"]),
                    ("name", ["clarify_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_string_length_empty_is_zero(self):
        # regression: unanswered ref -> length 0, condition True,
        # so the empty target is flagged (shown but empty)
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("occupation_other", [""]),
                    ("clarify_note", [""]),
                ],
                "survey": [
                    ("relevant", ["string-length(${occupation_other}) = 0"]),
                    ("name", ["clarify_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserCompositeFunctions:
    """coalesce / concat / if / int — combined with comparisons."""

    def test_coalesce_falls_through_to_second_ref(self):
        # numeric totals may live in either column; coalesce picks the filled one
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("income_cash", ["", "300"]),
                    ("income_kinda", ["50", ""]),
                    ("high_income_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["coalesce(${income_cash}, ${income_kinda}) > 100"]),
                    ("name", ["high_income_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # record 2: 400 > 100 -> shown & empty; record 1: 50 -> hidden
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_coalesce_both_empty_stays_null(self):
        # null coalesced with null remains null -> condition False -> hidden
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("income_cash", [""]),
                    ("income_kinda", [""]),
                    ("note", [""]),
                ],
                "survey": [
                    ("relevant", ["coalesce(${income_cash}, ${income_kinda}) > 100"]),
                    ("name", ["note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_concat_then_compare(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("region", ["north", "south"]),
                    ("district_code", ["N-01", "S-09"]),
                    ("north_region_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["concat(${region}, '-', ${district_code}) = 'north-N-01'"]),
                    ("name", ["north_region_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_concat_skips_null_parts(self):
        # null parts contribute '' rather than poisoning the result
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("prefix", ["AB"]),
                    ("mid", [""]),
                    ("suffix", ["CD"]),
                    ("probe", [""]),
                ],
                "survey": [
                    ("relevant", ["concat(${prefix}, ${mid}, ${suffix}) = 'ABCD'"]),
                    ("name", ["probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_if_selects_then_branch(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("age", ["19", "12"]),
                    ("adult_banner", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["if(${age} >= 18, 'adult', 'minor') = 'adult'"]),
                    ("name", ["adult_banner"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_if_selects_else_branch(self):
        # both records resolve to 'minor' -> condition False -> hidden & empty
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("age", ["9", "12"]),
                    ("banner", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["if(${age} >= 18, 'adult', 'minor') = 'adult'"]),
                    ("name", ["adult_banner"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_int_truncates_before_comparison(self):
        # int('7.9') = 7 -> 7 mod 2 = 1, not 0
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("n", ["7.9"]),
                    ("even_note", [""]),
                ],
                "survey": [
                    ("relevant", ["int(${n}) mod 2 = 0"]),
                    ("name", ["even_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_number_cast_on_string_column(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("qty_text", ["2.5", "10"]),
                    ("small_qty_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["number(${qty_text}) < 5"]),
                    ("name", ["small_qty_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1


class TestParserSumFunction:
    """sum() — row-wise addition across multiple refs, empty = 0."""

    def test_sum_two_columns_rowwise(self):
        # cash may be blank when value is recorded in-kind, and vice versa
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("income_cash", ["", "300", "50"]),
                    ("income_kinda", ["80", "", "60"]),
                    ("high_income_note", ["", "", "12"]),
                ],
                "survey": [
                    ("relevant", ["sum(${income_cash}, ${income_kinda}) > 100"]),
                    ("name", ["high_income_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # rec 1: 0 + 80 = 80 -> hidden & empty, ok
        # rec 2: 300 + 0 = 300 -> shown & empty -> violation
        # rec 3: 130 -> hidden & empty, ok
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_sum_three_columns_skips_null_parts(self):
        # regression: a null/empty part must contribute 0, not null the sum
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("a", ["AB", "10"]),
                    ("b", ["CD", ""]),
                    ("c", ["EF", "20"]),
                    ("code_probe", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["concat(${a}, ${b}, ${c}) = 'ABCDEF'"]),
                    ("name", ["code_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        # and the arithmetic version:
        result2 = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("a", ["5", "10"]),
                    ("b", ["", "20"]),
                    ("c", ["7", "30"]),
                    ("total_probe", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["sum(${a}, ${b}, ${c}) >= 57"]),
                    ("name", ["total_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # rec 2: 10 + 20 + 30 = 60 -> shown & empty
        do_basic_checks(result2, 1)
        assert result2[0].details is not None
        assert len(result2[0].details["uuid"]) == 1

    def test_sum_all_empty_is_zero(self):
        # unanswered everything -> sum = 0 -> condition False -> hidden & empty
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1]),
                    ("a", [""]),
                    ("b", [""]),
                    ("total_probe", [""]),
                ],
                "survey": [
                    ("relevant", ["sum(${a}, ${b}) > 0"]),
                    ("name", ["total_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_sum_single_arg(self):
        # sum(${x}) behaves like a forgiving numeric cast of one column
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("age", ["15", "25"]),
                    ("youth_note", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["sum(${age}) < 18"]),
                    ("name", ["youth_note"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1  # rec 1 only

    def test_sum_in_comparison_forces_numeric_cast(self):
        # string-typed export: 150 + 150 = 300, NOT string concat '150150'
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2]),
                    ("a", ["150", "150"]),
                    ("b", ["150", "150"]),
                    ("sum_probe", ["", ""]),
                ],
                "survey": [
                    ("relevant", ["sum(${a}, ${b}) = 300"]),
                    ("name", ["sum_probe"]),
                    ("required", ["yes"]),
                ],
            }
        )
        # string-concat trap (if sum fell through to '+') would give
        # '150150' != 300 -> never shown; numeric path flags both records
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2


class TestParserInvalidExpressions:
    """Malformed input must raise, not produce a wrong expression."""

    @pytest.mark.parametrize(
        "bad",
        [
            "${unclosed='x'",
            "'unbalanced",
            "${gender} =",  # dangling operator
            "and ${a}='b'",  # leading operator
            "${a}='x' extra_garbage",  # trailing tokens
            "unknown_fn(${a})",  # unsupported function
            "unknown_fn()",
            "selected(${a})",  # wrong arity
            "count-selected('a')",  # non-ref argument
            "selected(${reasons}, ${a})",
            "false(${reasons})",
            "starts-with(${a})",  # wrong arity
            "starts-with('a', 'b')",  # first arg must be a ref
            "starts-with(${a}, ${b})",  # second arg must be a literal
            "starts-with()",  # no arguments
            "ends-with(${a}, ${b})",  # non-literal suffix
            "ends-with('a', ${b})",
            "contains(${a})",  # wrong arity
            "contains(${a}, ${b})",
            "regex(${a})",  # missing pattern
            "regex(${a}, ${b})",
            "string-length()",  # no argument
            "string-length('a')",  # non-ref argument
            "coalesce(${a})",  # wrong arity
            "concat()",  # needs >= 1 argument
            "if(${a}='x', 'y')",  # wrong arity
            "int()",  # no argument
            "number(${a}, ${b})",  # wrong arity
            "sum()",  # no arguments
            "sum('a')",  # non-ref argument
            "sum(${a}, 'b')",  # mixed ref / literal
        ],
    )
    def test_malformed_raises(self, bad: str):

        schema = {"a": pl.String, "b": pl.Int64}
        with pytest.raises(Exception) as e:
            _ = build_relevance_expression(bad, schema)

        assert "Skip logic parser" in str(e.value)


class TestSchemaObjects:
    def test_missing_loaded_sheet(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey_missing": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is None
        assert "A data sheet for" in result[0].message

    def test_missing_loaded_column(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name_missing", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is None
        assert "A column for 'name'" in result[0].message

    def test_missing_id_column(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("id_Missing", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is None
        assert "Expected one unique id column for" in result[0].message

    def test_no_relevant_columns(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [("relevant", [""]), ("name", ["gender_other"]), ("required", ["yes"])],
            }
        )
        do_basic_checks(result, 0)

    def test_no_relevant_column_for_sheet(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender_diff}='other'"]),
                    ("name", ["diff"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_some_relevant_column_for_sheet(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", "bla"]),
                ],
                "survey": [
                    ("relevant", ["${gender_diff}='other'", "${gender}='other'"]),
                    ("name", ["diff", "gender_other"]),
                    ("required", ["yes", "yes"]),
                ],
            }
        )
        do_basic_checks(result, 0)

    def test_column_reference_on_other_sheet(self):
        result = run_skip_validation(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("gender_other", ["", "", ""]),
                ],
                "survey": [
                    ("relevant", ["${gender_diff}='other'"]),
                    ("name", ["gender_other"]),
                    ("required", ["yes"]),
                ],
            }
        )
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["sheet"][0] == "clean_data"
