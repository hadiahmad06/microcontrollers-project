#!/usr/bin/env python3
"""PreToolUse hook enforcing per-person docs folders (AGENTS.md section 3)."""
import json
import os
import re
import sys

# [AI-GENERATED: Claude Code]
SLUGS = ("hadi", "emanuel", "david-li", "david-leh")
FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

WRITE_RE = re.compile(
    r"(?<![\w./-])(tee|mv|cp|rm|touch|mkdir|rmdir|ln|truncate|dd)(?![\w./-])"
    r"|sed\s+(-\w*i\w*|--in-place)"
    r"|perl\s+-\w*i"
    r"|write_text|write_bytes"
    r"|open\s*\([^)]*['\"][wa]\+?b?['\"]"
)
REF_RE = re.compile(r"docs/(human|agent)/([A-Za-z0-9_-]+)/|docs/archive(?:/|\b)")
PERSON_RE = re.compile(r"docs/(human|agent)/([A-Za-z0-9_-]+)/")


def project_root():
    """Return the real project root path.

    Args: none.
    Returns: str, CLAUDE_PROJECT_DIR or the parent of this script's directory.
    """
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if not root:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.realpath(root)


def resolve_me(root):
    """Resolve the current person's slug.

    Args: root (str) project root.
    Returns: str slug, or None if unset/invalid.
    """
    me = os.environ.get("ME")
    if not me:
        try:
            with open(os.path.join(root, ".claude", "settings.local.json")) as f:
                me = (json.load(f).get("env") or {}).get("ME")
        except Exception:
            me = None
    return me if me in SLUGS else None


def check_path(path, cwd, root, me):
    """Decide whether a file tool may write to path.

    Args: path (str) target; cwd (str) base for relative paths; root (str)
        project root; me (str|None) identity.
    Returns: str block reason, or None to allow.
    """
    if not os.path.isabs(path):
        path = os.path.join(cwd or root, path)
    path = os.path.realpath(os.path.normpath(path))
    rel = os.path.relpath(path, root)
    if rel == ".." or rel.startswith(".." + os.sep):
        return None
    parts = rel.split(os.sep)
    if parts[:2] == ["docs", "archive"]:
        return "BLOCKED: docs/archive is read-only reference material."
    if len(parts) >= 3 and parts[0] == "docs" and parts[1] in ("human", "agent"):
        slug = parts[2]
        if slug in SLUGS or len(parts) >= 4:
            if me is None:
                return ("BLOCKED: identity not set; set ME in "
                        ".claude/settings.local.json ({\"env\": {\"ME\": \"<slug>\"}}) "
                        "with slug one of: " + ", ".join(SLUGS) + ".")
            if slug != me:
                return ("BLOCKED: agents only write to their own person's folders "
                        "(AGENTS.md section 3); you are '%s', target is '%s'." % (me, slug))
    return None


def check_bash(cmd, me):
    """Heuristically decide whether a shell command writes to a forbidden docs path.

    Args: cmd (str) shell command; me (str|None) identity.
    Returns: str block reason, or None to allow.
    """
    # strip harmless redirections (2>&1, >/dev/null)
    clean = re.sub(r"\d*>&\d+|\d*>>?\s*/dev/null", " ", cmd)
    if not (WRITE_RE.search(clean) or re.search(r"(?<![-=])>", clean)):
        return None
    for m in REF_RE.finditer(clean):
        if m.group(0).startswith("docs/archive"):
            return "BLOCKED: docs/archive is read-only reference material (bash write heuristic)."
        if m.group(2) != me:
            return ("BLOCKED: agents only write to their own person's folders "
                    "(AGENTS.md section 3); bash command touches docs/%s/%s/ "
                    "(ME=%s)." % (m.group(1), m.group(2), me))
    return None


def main():
    """Entry point: read hook JSON from stdin, exit 2 to block, 0 to allow.

    Args: none.
    Returns: int exit code.
    """
    try:
        data = json.loads(sys.stdin.read())
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except Exception as e:
        sys.stderr.write("guard_docs: warning: bad hook input (%s); allowing.\n" % e)
        return 0
    try:
        root = project_root()
        me = resolve_me(root)
        tool = data.get("tool_name", "")
        ti = data.get("tool_input") or {}
        reason = None
        if tool in FILE_TOOLS:
            p = ti.get("file_path") or ti.get("notebook_path")
            if p:
                reason = check_path(p, data.get("cwd"), root, me)
        elif tool == "Bash":
            reason = check_bash(ti.get("command") or "", me)
        if reason:
            sys.stderr.write(reason + "\n")
            return 2
    except Exception as e:
        sys.stderr.write("guard_docs: warning: internal error (%s); allowing.\n" % e)
    return 0
# [END AI-GENERATED]


if __name__ == "__main__":
    sys.exit(main())
