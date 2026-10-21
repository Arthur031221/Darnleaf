import json
import re
from importlib import resources

import pytest

from darnleaf import matcher

CODES = ["en", "zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de", "pt-BR"]


def load(code):
    return json.loads(resources.files("darnleaf").joinpath(f"web/locales/{code}.json").read_text(encoding="utf-8"))


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text))


def test_every_locale_has_the_same_keys_as_english():
    english = set(load("en"))
    for code in CODES:
        assert set(load(code)) == english, code


@pytest.mark.parametrize("code", CODES)
def test_every_reason_is_translated_with_the_same_placeholders(code):
    strings = load(code)
    for key, english in matcher.REASONS.items():
        assert placeholders(strings[f"reason.{key}"]) == placeholders(english), (code, key)


def test_english_locale_matches_the_matcher_wording():
    strings = load("en")
    for key, english in matcher.REASONS.items():
        assert strings[f"reason.{key}"] == english


def test_a_proposal_reports_its_reason_key_and_arguments():
    p = matcher.Proposal(0, 4, "check", "close", {"page": 6, "margin": "0.02"}, [])
    out = p.public()
    assert out["reason"] == "page 6 scores almost as high (margin 0.02)"
    assert (out["reason_key"], out["reason_args"]) == ("close", {"page": 6, "margin": "0.02"})
