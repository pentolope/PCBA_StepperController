"""Evidence governance this board declares, as data.

The manifest generator merges these blocks into its own document, so the
committed manifest and the generated one agree by construction - the
same discipline every other derived document lives under. The content
lives in governance.json beside this module; the merge logic is
`merged` below.
"""
import copy
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "governance.json")
with open(_PATH, encoding="utf-8") as _handle:
    _DATA = json.load(_handle)

TOP = _DATA["top"]
EXTRA_MANDATORY_GATES = _DATA["extra_mandatory_gates"]
EXTRA_REQUIRED_EVIDENCE = _DATA["extra_required_evidence"]
REQUIRED_DOMAINS = _DATA["required_domains"]
DECLINED_DOMAINS = _DATA["declined_domains"]
EXTRA_SOURCE_CLOSURE = _DATA["extra_source_closure"]


def merged(document):
    doc = copy.deepcopy(document)
    doc.update(copy.deepcopy(TOP))
    profile = doc["release_profile"]
    profile["mandatory_gates"] = sorted(
        set(profile["mandatory_gates"]) | set(EXTRA_MANDATORY_GATES))
    profile["required_evidence"] = sorted(
        set(profile.get("required_evidence", []))
        | set(EXTRA_REQUIRED_EVIDENCE))
    profile["required_domains"] = list(REQUIRED_DOMAINS)
    profile["declined_domains"] = copy.deepcopy(DECLINED_DOMAINS)
    closure = doc["reports"]["source_closure"]
    for pattern in EXTRA_SOURCE_CLOSURE:
        if pattern not in closure:
            closure.append(pattern)
    return doc
