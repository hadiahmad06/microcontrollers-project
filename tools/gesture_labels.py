#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Gesture label names (C5.1, decided). Index = class id 0..8.

Used by recorder.py, dataset_tool.py and fake_wand.py (ticket W2-4).
"""

LABELS = ("none", "swipe_right", "swipe_left", "raise", "push_down", "circle_cw",
          "circle_ccw", "twist", "thrust")


def parse_label(s):
    """Turn a decimal class id or a label name into a class id.

    Args:
        s: str (or int). A decimal id 0..8, or a name from LABELS (case-insensitive,
            '-' and '_' are equivalent).
    Returns:
        int class id 0..8.
    Raises:
        ValueError: if s is neither; the message names the valid labels.
    """
    t = str(s).strip().lower().replace("-", "_")
    if t.isdigit() and int(t) < len(LABELS):
        return int(t)
    if t in LABELS:
        return LABELS.index(t)
    raise ValueError("bad label %r; valid: %s (or 0..%d)" % (s, ", ".join(LABELS), len(LABELS) - 1))
# [END AI-GENERATED]
