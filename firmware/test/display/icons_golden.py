# [AI-GENERATED: Claude Code]
"""Golden table for the icon identity test (ticket WP4-aF, review finding M1 of WP4-aR).

This is a REGRESSION SNAPSHOT of a design choice, not a spec: the bitmaps and colours below were
copied from firmware/src/icons.c as committed at WP4-aF. The suite fails if any icon bitmap or
colour changes, or if two ids swap. If the team deliberately redesigns an icon, update the entry
here in the same commit (the failure message names the id).

Format: id -> (8 bitmap bytes as 16 hex digits, byte 0 = top row, bit 7 = leftmost column;
(R, G, B) raw colour before the display cap).
"""

GOLDEN = {
    -1: ("3C66060C18180018", (255, 128, 0)),     # UNKNOWN: question mark, orange
    0: ("0000000000000000", (0, 0, 0)),          # NONE: blank
    1: ("1018FEFFFE181000", (255, 0, 0)),        # SWIPE_RIGHT: arrow right, red
    2: ("08187FFF7F180800", (0, 0, 255)),        # SWIPE_LEFT: arrow left, blue
    3: ("183C7EFF18181818", (0, 255, 0)),        # RAISE: arrow up, green
    4: ("18181818FF7E3C18", (255, 255, 0)),      # PUSH_DOWN: arrow down, yellow
    5: ("3C42878281423C00", (0, 255, 255)),      # CIRCLE_CW, cyan
    6: ("3C42E14181423C00", (255, 0, 255)),      # CIRCLE_CCW, magenta
    7: ("FF7E3C18183C7EFF", (255, 255, 255)),    # TWIST: hourglass, white
    8: ("3C4299A5A599423C", (255, 64, 64)),      # THRUST: target, salmon
    9: ("1838181818187E00", (160, 0, 255)),      # learned slot 1: digit 1, purple
    10: ("3C66060C18307E00", (160, 0, 255)),     # learned slot 2: digit 2
    11: ("3C66061C06663C00", (160, 0, 255)),     # learned slot 3: digit 3
    12: ("0C1C3C6C7E0C0C00", (160, 0, 255)),     # learned slot 4: digit 4
    100: ("000103068CD87020", (0, 255, 0)),      # ICON_LEARN_OK: check mark, green
}

# Pairs (a, b, kind): icon b is the mirror image of icon a. "lr" = left-right (reverse the bits of
# every row), "tb" = top-bottom (reverse the row order). All three hold in the WP4-aF snapshot.
MIRRORS = [
    (5, 6, "lr"),   # CIRCLE_CW / CIRCLE_CCW
    (1, 2, "lr"),   # SWIPE_RIGHT / SWIPE_LEFT
    (3, 4, "tb"),   # RAISE / PUSH_DOWN
]
# [END AI-GENERATED]
