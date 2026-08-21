"""Shared LLM-response JSON extraction (H1).

`decision.py`, `learning.py` and `appraisal.py` each ask the fast model for a
JSON object embedded in free text and used to pull it out with
`re.search(r"\\{.*\\}", text, re.DOTALL)`. That regex is greedy: it matches
from the FIRST `{` to the LAST `}` anywhere in the response. If the model
emits a stray example object, an aside containing braces, or leftover
chain-of-thought around the real answer, the match spans everything between
them and `json.loads` fails on the resulting garbage.

`extract_json_blocks` finds every syntactically complete top-level
object/array by bracket-depth counting instead, so it stops at the first
block's own closing bracket rather than the text's last one. It is
string/escape aware so braces inside a quoted JSON string value don't perturb
the depth count.
"""

import json
from typing import Any

_OPENERS = {"{": "}", "[": "]"}


def extract_json_blocks(text: str, brackets: str = "{[") -> list[str]:
    """Return every syntactically-complete top-level JSON block in `text`,
    in order of appearance. `brackets` restricts which opening characters
    start a candidate block (e.g. pass "{" to only ever consider objects).
    """
    blocks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in brackets:
            closer = _OPENERS[ch]
            stack = [closer]
            in_string = False
            escape = False
            j = i + 1
            well_formed = False
            while j < n:
                c = text[j]
                if in_string:
                    if escape:
                        escape = False
                    elif c == "\\":
                        escape = True
                    elif c == '"':
                        in_string = False
                else:
                    if c == '"':
                        in_string = True
                    elif c in _OPENERS:
                        stack.append(_OPENERS[c])
                    elif c in ("}", "]"):
                        if not stack or stack[-1] != c:
                            break  # mismatched bracket; abandon this start
                        stack.pop()
                        if not stack:
                            well_formed = True
                            j += 1
                            break
                j += 1
            if well_formed:
                blocks.append(text[i:j])
                i = j
                continue
        i += 1
    return blocks


def extract_first_json_value(text: str, brackets: str = "{[") -> Any | None:
    """Parse and return the first top-level JSON block in `text` that
    actually parses, trying candidates in order of appearance. Returns None
    if none of them parse.
    """
    for block in extract_json_blocks(text, brackets=brackets):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            continue
    return None
