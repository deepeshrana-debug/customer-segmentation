import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from summary import check_numbers, parse_list, percentages, sentences  # noqa: E402


def test_percentage_of_total():
    values = {"total": 1000, "most": 233}
    assert percentages(values)["most"] == 23.3


def test_percentages_skip_the_total():
    values = {"total": 1000, "most": 233, "least": 334}
    result = percentages(values)
    assert "total" not in result
    assert result["least"] == 33.4


def test_percentages_are_rounded_to_one_decimal():
    values = {"total": 3, "most": 1}
    assert percentages(values)["most"] == 33.3


def test_percentages_handle_zero_total():
    assert percentages({"total": 0, "most": 5}) == {}
    assert percentages({"most": 5}) == {}


def test_percentage_of_everything_is_one_hundred():
    values = {"total": 400, "most": 400}
    assert percentages(values)["most"] == 100.0


def test_missing_boxes_are_skipped():
    result = percentages({"total": 100})
    assert result == {}


def test_parse_simple_list():
    text = "Most buyers: 233\nLeast buyers: 334\nFrequent buyers: 798\nBought last month: 24"
    values, unknown = parse_list(text)

    assert unknown == []
    assert values == {
        "most": 233,
        "least": 334,
        "frequent": 798,
        "last_month": 24,
    }


def test_parse_ignores_capital_letters_and_extra_spaces():
    text = "  MOST   BUYERS :   5  \n\tleast buyers:\t7"
    values, unknown = parse_list(text)

    assert unknown == []
    assert values == {"most": 5, "least": 7}


def test_parse_skips_blank_lines():
    values, unknown = parse_list("\n\nMost buyers: 1\n\n\n")
    assert unknown == []
    assert values == {"most": 1}


def test_parse_reports_lines_it_does_not_understand():
    text = "Most buyers: 10\nthis line is nonsense\nLeast buyers: 2"
    values, unknown = parse_list(text)

    assert values == {"most": 10, "least": 2}
    assert unknown == ["this line is nonsense"]


def test_parse_rejects_unknown_names():
    values, unknown = parse_list("Banana buyers: 4")
    assert values == {}
    assert unknown == ["Banana buyers: 4"]


def test_parse_rejects_numbers_that_are_not_whole():
    for bad in ["Most buyers: 12.5", "Most buyers: -3", "Most buyers: lots"]:
        values, unknown = parse_list(bad)
        assert values == {}, f"{bad!r} should not be accepted"
        assert unknown == [bad]


def test_parse_accepts_zero():
    values, unknown = parse_list("Least buyers: 0")
    assert values == {"least": 0}
    assert unknown == []


def test_parse_empty_text():
    assert parse_list("") == ({}, [])
    assert parse_list(None) == ({}, [])


def test_total_too_small_warning():
    values = {"total": 10, "most": 500}
    warnings = check_numbers(values)
    assert "Total buyers looks too small. Please check the numbers." in warnings


def test_three_groups_must_add_up():
    values = {"total": 1000, "most": 233, "regular": 100, "least": 334}
    warnings = check_numbers(values)
    assert any("add up to 667, not 1,000" in w for w in warnings)


def test_matching_groups_give_no_warning():
    values = {"total": 1000, "most": 233, "regular": 433, "least": 334}
    assert check_numbers(values) == []


def test_sentences_use_the_real_numbers():
    values = {
        "total": 1000,
        "most": 233,
        "regular": 433,
        "least": 334,
        "last_month": 24,
    }
    text = sentences(values)

    assert any("Out of 1,000 buyers" in s for s in text)
    assert any("24 buyers bought last month" in s for s in text)


def test_sentence_says_one_buyer_not_buyers():
    text = sentences({"buyers": 0, "last_month": 1, "total": 10})
    assert any("1 buyer bought last month." == s for s in text)


def test_sentences_advice_follows_biggest_group():
    values = {"total": 1000, "most": 100, "regular": 100, "least": 800}
    text = sentences(values)
    assert any("second-purchase offer" in s for s in text)


def test_sentences_never_make_up_numbers():
    assert sentences({}) == []


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
