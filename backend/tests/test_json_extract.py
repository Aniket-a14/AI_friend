from app.cognitive.json_extract import extract_first_json_value, extract_json_blocks


def test_stops_at_first_blocks_own_closing_brace_not_the_texts_last_one():
    """The exact failure mode in H1: a greedy `\\{.*\\}` regex spans from the
    first `{` to the last `}` in the whole response. Two independent JSON
    objects separated by prose must be extracted as two blocks, not fused
    into one invalid span covering the text between them.
    """
    text = 'Sure, {"a": 1} and also here is another example {"b": 2}.'
    blocks = extract_json_blocks(text)
    assert blocks == ['{"a": 1}', '{"b": 2}']


def test_first_json_value_returns_the_first_block_that_actually_parses():
    text = 'Sure, {"a": 1} and also here is another example {"b": 2}.'
    assert extract_first_json_value(text) == {"a": 1}


def test_survives_stray_braces_inside_a_quoted_string_value():
    text = '{"note": "use braces like { and } in code"}'
    assert extract_first_json_value(text) == {"note": "use braces like { and } in code"}


def test_survives_nested_objects():
    text = 'noise before {"outer": {"inner": [1, 2, 3]}} noise after'
    assert extract_first_json_value(text) == {"outer": {"inner": [1, 2, 3]}}


def test_returns_none_when_nothing_parses():
    assert extract_first_json_value("no json here at all") is None


def test_recovers_the_real_object_after_an_unterminated_brace_in_prose():
    """A stray unmatched `{` earlier in the text (e.g. the model narrating
    "I'll format it like { ... " before actually answering) must not prevent
    finding the real, well-formed block that follows.
    """
    text = 'I will format it like { but here is the real answer: {"ok": true}'
    assert extract_first_json_value(text) == {"ok": True}


def test_brackets_param_restricts_which_opener_starts_a_candidate():
    text = '["a", "b"] and {"c": 1}'
    assert extract_json_blocks(text, brackets="{") == ['{"c": 1}']
    assert extract_json_blocks(text, brackets="[") == ['["a", "b"]']
