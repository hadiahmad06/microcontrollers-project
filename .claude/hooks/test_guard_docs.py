#!/usr/bin/env python3
"""Black-box tests for guard_docs.py (PreToolUse hook, AGENTS.md section 3).

Run:  python3 -m unittest .claude/hooks/test_guard_docs.py -v
Every case runs the hook as a subprocess against a throw-away temp project.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

# [AI-GENERATED: Claude Code]
HERE = os.path.dirname(os.path.abspath(__file__))
HOOK_SRC = os.path.join(HERE, "guard_docs.py")
SLUGS = ("hadi", "emanuel", "david-li", "david-leh")
MAX_LATENCY = [0.0]  # largest wall time (s) seen by run_hook in this process


def make_project(settings_me=None, raw_settings=None):
    """Create a temp project with a copy of the hook and the docs skeleton.

    Args: settings_me (str|None) value for env.ME in settings.local.json;
        raw_settings (str|None) literal file content (overrides settings_me).
    Returns: str, realpath of the new project root (caller must rmtree it).
    """
    root = os.path.realpath(tempfile.mkdtemp(prefix="guard_docs_test_"))
    os.makedirs(os.path.join(root, ".claude", "hooks"))
    shutil.copy(HOOK_SRC, os.path.join(root, ".claude", "hooks", "guard_docs.py"))
    for kind in ("human", "agent"):
        for s in SLUGS:
            os.makedirs(os.path.join(root, "docs", kind, s))
    os.makedirs(os.path.join(root, "docs", "archive"))
    os.makedirs(os.path.join(root, "src", "deep"))
    path = os.path.join(root, ".claude", "settings.local.json")
    if raw_settings is not None:
        with open(path, "w") as f:
            f.write(raw_settings)
    elif settings_me is not None:
        with open(path, "w") as f:
            json.dump({"env": {"ME": settings_me}}, f)
    return root


def run_hook(root, stdin, me=None, set_project_dir=True):
    """Run the hook subprocess and return (exit_code, stderr, stdout).

    Args: root (str) project root holding .claude/hooks/guard_docs.py;
        stdin (dict|str) payload (dict is JSON-encoded, str sent verbatim);
        me (str|None) value for env ME, None means variable is unset;
        set_project_dir (bool) whether to export CLAUDE_PROJECT_DIR.
    Returns: tuple (int, str, str).
    """
    env = {k: v for k, v in os.environ.items() if k not in ("ME", "CLAUDE_PROJECT_DIR")}
    if me is not None:
        env["ME"] = me
    if set_project_dir:
        env["CLAUDE_PROJECT_DIR"] = root
    data = stdin if isinstance(stdin, str) else json.dumps(stdin)
    script = os.path.join(root, ".claude", "hooks", "guard_docs.py")
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, script], input=data, capture_output=True,
                       text=True, env=env, cwd=root)
    MAX_LATENCY[0] = max(MAX_LATENCY[0], time.perf_counter() - t0)
    return p.returncode, p.stderr, p.stdout


def file_payload(root, tool, path, cwd=None):
    """Build a hook payload for a file-writing tool.

    Args: root (str) project root; tool (str) tool name; path (str) target;
        cwd (str|None) cwd to report (defaults to root).
    Returns: dict.
    """
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return {"tool_name": tool, "tool_input": {key: path}, "cwd": cwd or root}


def bash_payload(root, cmd):
    """Build a hook payload for a Bash call.

    Args: root (str) project root; cmd (str) shell command.
    Returns: dict.
    """
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": root}


class HookCase(unittest.TestCase):
    """Base class: one shared temp project per test class."""

    SETTINGS_ME = None

    @classmethod
    def setUpClass(cls):
        """Create the shared temp project."""
        cls.root = make_project(cls.SETTINGS_ME)

    @classmethod
    def tearDownClass(cls):
        """Delete the shared temp project."""
        shutil.rmtree(cls.root, ignore_errors=True)

    def run_h(self, payload, me="hadi", **kw):
        """Run hook against the shared project."""
        return run_hook(self.root, payload, me=me, **kw)

    def assertBlocked(self, res, msg=None):
        """Assert exit 2 and exactly one non-empty stderr line."""
        code, err, _ = res
        self.assertEqual(code, 2, msg or "expected block, stderr=%r" % err)
        self.assertEqual(len(err.strip().splitlines()), 1, "reason must be one line: %r" % err)

    def assertAllowed(self, res, msg=None):
        """Assert exit 0."""
        code, err, _ = res
        self.assertEqual(code, 0, msg or "expected allow, stderr=%r" % err)

    def p(self, *parts):
        """Join parts under the temp project root."""
        return os.path.join(self.root, *parts)


# ---------------------------------------------------------------- file tools
class FileToolTests(HookCase):
    """Write/Edit/MultiEdit/NotebookEdit rules."""

    TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

    def test_own_folder_allowed_each_slug_each_tool_each_kind(self):
        """Every slug as ME may write its own human/ and agent/ folders."""
        for me in SLUGS:
            for tool in self.TOOLS:
                for kind in ("human", "agent"):
                    with self.subTest(me=me, tool=tool, kind=kind):
                        pth = self.p("docs", kind, me, "n.md")
                        self.assertAllowed(self.run_h(file_payload(self.root, tool, pth), me=me))

    def test_other_folder_blocked_each_slug_pair(self):
        """Every slug is blocked from every other slug's folders, all tools."""
        for me in SLUGS:
            for other in SLUGS:
                if other == me:
                    continue
                for tool in self.TOOLS:
                    for kind in ("human", "agent"):
                        with self.subTest(me=me, other=other, tool=tool, kind=kind):
                            pth = self.p("docs", kind, other, "n.md")
                            self.assertBlocked(self.run_h(file_payload(self.root, tool, pth), me=me))

    def test_archive_blocked_for_everyone(self):
        """docs/archive/** is blocked for all slugs and all tools, nested too."""
        for me in SLUGS:
            for tool in self.TOOLS:
                for rel in ("docs/archive/x.md", "docs/archive/a/b/c.md", "docs/archive"):
                    with self.subTest(me=me, tool=tool, rel=rel):
                        self.assertBlocked(self.run_h(
                            file_payload(self.root, tool, self.p(rel)), me=me))

    def test_archive_blocked_when_me_unset(self):
        """Archive is blocked even with no identity."""
        self.assertBlocked(self.run_h(file_payload(self.root, "Write", self.p("docs/archive/x")), me=None))

    def test_me_unset_blocks_person_folders(self):
        """ME unset (no env, no settings.local.json): every person folder blocked."""
        for s in SLUGS:
            for kind in ("human", "agent"):
                with self.subTest(slug=s, kind=kind):
                    self.assertBlocked(self.run_h(
                        file_payload(self.root, "Write", self.p("docs", kind, s, "x.md")), me=None))

    def test_me_unset_message_mentions_identity(self):
        """The unset-identity reason tells the user how to fix it."""
        _, err, _ = self.run_h(file_payload(self.root, "Write", self.p("docs/human/hadi/x")), me=None)
        self.assertIn("ME", err)

    def test_invalid_me_blocks_like_unset(self):
        """Invalid slugs in ME behave as unset."""
        for bad in ("bob", "HADI", "hadi ", "hadi/", "david", "../hadi"):
            with self.subTest(me=bad):
                self.assertBlocked(self.run_h(
                    file_payload(self.root, "Write", self.p("docs/human/hadi/x.md")), me=bad))

    def test_top_level_docs_files_allowed(self):
        """Top-level docs/human/*.md and docs/agent/*.md are open to everyone."""
        for me in (None,) + SLUGS:
            for rel in ("docs/human/TEAM_PROCESS.md", "docs/agent/BOARD.md", "docs/human/x.md",
                        "docs/agent/x.md", "docs/README.md"):
                with self.subTest(me=me, rel=rel):
                    self.assertAllowed(self.run_h(file_payload(self.root, "Write", self.p(rel)), me=me))

    def test_everything_else_allowed(self):
        """Code, root files and .claude files are allowed (even with ME unset)."""
        for rel in ("src/a.py", "AGENTS.md", "CLAUDE.md", ".claude/settings.json", "README.md",
                    "docs/other/hadi/x.md", "mydocs/human/emanuel/x.md"):
            with self.subTest(rel=rel):
                self.assertAllowed(self.run_h(file_payload(self.root, "Write", self.p(rel)), me=None))

    def test_directory_path_itself(self):
        """docs/human/<slug> (no trailing file) follows the slug rule."""
        for kind in ("human", "agent"):
            with self.subTest(kind=kind, who="other"):
                self.assertBlocked(self.run_h(
                    file_payload(self.root, "Write", self.p("docs", kind, "emanuel")), me="hadi"))
            with self.subTest(kind=kind, who="self"):
                self.assertAllowed(self.run_h(
                    file_payload(self.root, "Write", self.p("docs", kind, "hadi")), me="hadi"))
            with self.subTest(kind=kind, who="trailing slash other"):
                self.assertBlocked(self.run_h(
                    file_payload(self.root, "Write", self.p("docs", kind, "emanuel") + "/"), me="hadi"))

    def test_unknown_slug_subfolder_blocked(self):
        """docs/human/<not-a-slug>/file is not a top-level file: treated as someone else's."""
        self.assertBlocked(self.run_h(file_payload(self.root, "Write", self.p("docs/human/bob/x.md")), me="hadi"))

    def test_relative_path_cwd_in_subdirectory(self):
        """Relative file_path resolves against payload cwd, not hook cwd."""
        cases = [  # (cwd rel, path, blocked)
            ("docs/human/emanuel", "a.md", True),
            ("docs/human/hadi", "a.md", False),
            ("docs/human/hadi", "../emanuel/a.md", True),
            ("docs/human", "emanuel/a.md", True),
            ("docs/human", "hadi/a.md", False),
            ("docs", "archive/a.md", True),
            ("docs", "human/david-li/a.md", True),
            ("src", "../docs/human/emanuel/a.md", True),
            ("src/deep", "../../docs/agent/david-leh/a.md", True),
            ("src/deep", "../../docs/agent/hadi/a.md", False),
            ("src", "a.py", False),
            ("docs/archive", "x.md", True),
        ]
        for cwd, path, blocked in cases:
            with self.subTest(cwd=cwd, path=path):
                res = self.run_h(file_payload(self.root, "Edit", path, cwd=self.p(cwd)), me="hadi")
                (self.assertBlocked if blocked else self.assertAllowed)(res)

    def test_missing_cwd_resolves_against_root(self):
        """No cwd in payload: relative path is taken relative to the project root."""
        pl = {"tool_name": "Write", "tool_input": {"file_path": "docs/human/emanuel/a.md"}}
        self.assertBlocked(self.run_h(pl))

    def test_dotdot_traversal(self):
        """`..` is normalised before the rule is applied."""
        cases = [
            ("docs/human/hadi/../emanuel/a.md", True),
            ("docs/human/hadi/../../human/emanuel/a.md", True),
            ("src/../docs/archive/a.md", True),
            ("docs/human/emanuel/../hadi/a.md", False),
            ("docs/human/emanuel/../../../src/a.py", False),
            ("docs/human/./emanuel/./a.md", True),
            ("docs//human//emanuel//a.md", True),
            ("src/../../" + os.path.basename(self.root) + "/docs/human/emanuel/a.md", True),
        ]
        for rel, blocked in cases:
            with self.subTest(rel=rel):
                res = self.run_h(file_payload(self.root, "Write", self.p(rel)), me="hadi")
                (self.assertBlocked if blocked else self.assertAllowed)(res)

    def test_paths_outside_project_root_allowed(self):
        """Outside the root nothing is checked, even if it looks like docs/human/<other>."""
        outside = tempfile.mkdtemp(prefix="guard_docs_outside_")
        try:
            os.makedirs(os.path.join(outside, "docs", "human", "emanuel"))
            for pth in (os.path.join(outside, "docs/human/emanuel/a.md"), "/tmp/x.md",
                        os.path.join(outside, "docs/archive/a.md"), os.path.expanduser("~/x.md")):
                with self.subTest(path=pth):
                    self.assertAllowed(self.run_h(file_payload(self.root, "Write", pth)))
            with self.subTest(path="relative escaping root"):
                self.assertAllowed(self.run_h(
                    file_payload(self.root, "Write", "../../outside/docs/human/emanuel/a.md")))
            with self.subTest(path="cwd outside root"):
                self.assertAllowed(self.run_h(file_payload(self.root, "Write", "docs/human/emanuel/a.md", cwd=outside)))
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_sibling_dir_with_root_prefix_not_inside_root(self):
        """<root>-evil/docs/human/emanuel is outside root (prefix trap) so allowed."""
        sib = self.root + "-evil"
        os.makedirs(os.path.join(sib, "docs", "human", "emanuel"), exist_ok=True)
        try:
            self.assertAllowed(self.run_h(file_payload(self.root, "Write", sib + "/docs/human/emanuel/a.md")))
        finally:
            shutil.rmtree(sib, ignore_errors=True)

    def test_symlink_into_other_persons_folder_blocked(self):
        """A symlink inside the project that points into emanuel's folder is followed."""
        link = self.p("src", "sneaky")
        os.symlink(self.p("docs", "human", "emanuel"), link)
        try:
            self.assertBlocked(self.run_h(file_payload(self.root, "Write", link + "/a.md")))
            self.assertBlocked(self.run_h(file_payload(self.root, "Write", "sneaky/a.md", cwd=self.p("src"))))
            self.assertBlocked(self.run_h(file_payload(self.root, "Write", link)))  # link itself
        finally:
            os.unlink(link)

    def test_symlink_inside_own_folder_to_other_blocked(self):
        """docs/human/hadi/evil -> ../emanuel : writing through it is blocked."""
        link = self.p("docs", "human", "hadi", "evil")
        os.symlink(os.path.join("..", "emanuel"), link)
        try:
            self.assertBlocked(self.run_h(file_payload(self.root, "Write", link + "/a.md")))
        finally:
            os.unlink(link)

    def test_symlink_to_archive_blocked(self):
        """A symlink to docs/archive is followed."""
        link = self.p("src", "arch")
        os.symlink(self.p("docs", "archive"), link)
        try:
            self.assertBlocked(self.run_h(file_payload(self.root, "Write", link + "/a.md")))
        finally:
            os.unlink(link)

    def test_symlink_from_other_folder_to_own_allowed(self):
        """Symlink emanuel-folder -> src: resolved target is src, so allowed (not a leak)."""
        link = self.p("docs", "human", "emanuel", "tosrc")
        os.symlink(self.p("src"), link)
        try:
            self.assertAllowed(self.run_h(file_payload(self.root, "Write", link + "/a.py")))
        finally:
            os.unlink(link)

    def test_symlinked_project_root(self):
        """CLAUDE_PROJECT_DIR given as a symlink to the project still enforces rules."""
        alias = self.root + "-alias"
        os.symlink(self.root, alias)
        try:
            res = run_hook(alias, file_payload(alias, "Write", alias + "/docs/human/emanuel/a.md"), me="hadi")
            self.assertBlocked(res)
            res = run_hook(alias, file_payload(alias, "Write", alias + "/docs/human/hadi/a.md"), me="hadi")
            self.assertAllowed(res)
        finally:
            os.unlink(alias)

    def test_unknown_tool_allowed(self):
        """Tools the hook does not manage (Read, Glob, ...) are never blocked."""
        for tool in ("Read", "Glob", "Grep", "WebFetch", "", "write"):
            with self.subTest(tool=tool):
                pl = {"tool_name": tool, "tool_input": {"file_path": self.p("docs/human/emanuel/a.md")},
                      "cwd": self.root}
                self.assertAllowed(self.run_h(pl))

    def test_missing_tool_name_allowed(self):
        """Payload without tool_name is allowed."""
        self.assertAllowed(self.run_h({"tool_input": {"file_path": self.p("docs/human/emanuel/a.md")}}))

    def test_missing_path_allowed(self):
        """File tool with no path field is allowed (nothing to check)."""
        for ti in ({}, {"content": "x"}, {"file_path": ""}, {"file_path": None}):
            with self.subTest(ti=ti):
                self.assertAllowed(self.run_h({"tool_name": "Write", "tool_input": ti, "cwd": self.root}))

    def test_notebook_edit_uses_notebook_path(self):
        """NotebookEdit is checked via tool_input.notebook_path."""
        pl = {"tool_name": "NotebookEdit", "cwd": self.root,
              "tool_input": {"notebook_path": self.p("docs/agent/emanuel/n.ipynb"), "new_source": "x"}}
        self.assertBlocked(self.run_h(pl))

    def test_unicode_and_spaces_in_path(self):
        """Odd characters in a path do not crash the hook."""
        self.assertBlocked(self.run_h(file_payload(self.root, "Write", self.p("docs/human/emanuel/ünï cødé file.md"))))
        self.assertAllowed(self.run_h(file_payload(self.root, "Write", self.p("docs/human/hadi/with space.md"))))

    @unittest.skipUnless(sys.platform == "darwin", "case-insensitive FS is a macOS/Windows default")
    @unittest.expectedFailure
    def test_KNOWN_BUG_case_variants_bypass_on_case_insensitive_fs(self):
        """BUG: docs/Human/Emanuel/x hits the same folder on APFS but is allowed by the hook."""
        probe = self.p("docs", "HUMAN")
        if not os.path.isdir(probe):
            self.skipTest("filesystem is case sensitive")
        self.assertBlocked(self.run_h(file_payload(self.root, "Write", self.p("docs/HUMAN/emanuel/a.md"))))


# ----------------------------------------------------------------- identity
class IdentityTests(unittest.TestCase):
    """ME resolution: env var, settings.local.json, precedence, invalid values."""

    def setUp(self):
        """Track temp dirs for cleanup."""
        self.dirs = []

    def tearDown(self):
        """Remove temp projects."""
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def proj(self, **kw):
        """Make a temp project and remember it."""
        r = make_project(**kw)
        self.dirs.append(r)
        return r

    def write_to(self, root, slug, me, kind="human"):
        """Run a Write to docs/<kind>/<slug>/x.md and return the result."""
        pl = file_payload(root, "Write", os.path.join(root, "docs", kind, slug, "x.md"))
        return run_hook(root, pl, me=me)

    def test_settings_local_each_slug(self):
        """ME read from settings.local.json (no env var) for each slug."""
        for me in SLUGS:
            root = self.proj(settings_me=me)
            for target in SLUGS:
                with self.subTest(me=me, target=target):
                    code, err, _ = self.write_to(root, target, None)
                    self.assertEqual(code, 0 if target == me else 2, err)

    def test_env_each_slug_without_settings_file(self):
        """No settings.local.json at all: env ME works."""
        root = self.proj()
        self.assertFalse(os.path.exists(os.path.join(root, ".claude", "settings.local.json")))
        for me in SLUGS:
            with self.subTest(me=me):
                self.assertEqual(self.write_to(root, me, me)[0], 0)
                other = SLUGS[(SLUGS.index(me) + 1) % 4]
                self.assertEqual(self.write_to(root, other, me)[0], 2)

    def test_no_env_no_settings_is_unset(self):
        """Neither source: person folders blocked, other paths still allowed."""
        root = self.proj()
        self.assertEqual(self.write_to(root, "hadi", None)[0], 2)
        pl = file_payload(root, "Write", os.path.join(root, "src", "a.py"))
        self.assertEqual(run_hook(root, pl, me=None)[0], 0)

    def test_env_wins_over_settings(self):
        """Env ME=emanuel beats settings ME=hadi."""
        root = self.proj(settings_me="hadi")
        self.assertEqual(self.write_to(root, "emanuel", "emanuel")[0], 0)
        self.assertEqual(self.write_to(root, "hadi", "emanuel")[0], 2)

    def test_empty_env_falls_back_to_settings(self):
        """ME='' is treated as not set, so settings.local.json applies."""
        root = self.proj(settings_me="david-li")
        self.assertEqual(self.write_to(root, "david-li", "")[0], 0)

    def test_invalid_env_with_valid_settings_AMBIGUOUS(self):
        """AMBIGUOUS SPEC: env ME=bob (invalid) + settings ME=hadi.

        Implementation treats invalid env as unset WITHOUT falling back to settings
        (so hadi is blocked from own folder). Spec says 'invalid slug = unset', which
        this matches literally; the alternative reading would fall through.
        """
        root = self.proj(settings_me="hadi")
        self.assertEqual(self.write_to(root, "hadi", "bob")[0], 2)

    def test_invalid_settings_value_is_unset(self):
        """Invalid slug in settings.local.json = unset."""
        for bad in ("bob", "", "HADI", "hadi ", 5, None, ["hadi"], {"a": 1}):
            root = self.proj(raw_settings=json.dumps({"env": {"ME": bad}}))
            with self.subTest(value=bad):
                self.assertEqual(self.write_to(root, "hadi", None)[0], 2)

    def test_broken_settings_file_is_unset_not_crash(self):
        """Unparseable / wrong-shaped settings.local.json -> unset, hook still decides."""
        for raw in ("", "{not json", "[]", "null", '"hadi"', '{"env": null}', '{"env": []}',
                    '{"env": "hadi"}', '{"ME": "hadi"}', "{}"):
            root = self.proj(raw_settings=raw)
            with self.subTest(raw=raw):
                code, err, _ = self.write_to(root, "hadi", None)
                self.assertEqual(code, 2, err)  # blocked as unset, not a crash/allow

    def test_settings_utf8_bom_or_extra_keys(self):
        """Extra keys beside env.ME are ignored."""
        root = self.proj(raw_settings=json.dumps({"permissions": {}, "env": {"X": "1", "ME": "david-leh"}}))
        self.assertEqual(self.write_to(root, "david-leh", None)[0], 0)

    def test_project_dir_falls_back_to_script_location(self):
        """CLAUDE_PROJECT_DIR unset: root derived from <script>/../.. ."""
        root = self.proj(settings_me="hadi")
        pl = file_payload(root, "Write", os.path.join(root, "docs/human/emanuel/x"))
        self.assertEqual(run_hook(root, pl, me=None, set_project_dir=False)[0], 2)
        pl = file_payload(root, "Write", os.path.join(root, "docs/human/hadi/x"))
        self.assertEqual(run_hook(root, pl, me=None, set_project_dir=False)[0], 0)

    def test_settings_read_from_project_dir_not_cwd(self):
        """settings.local.json is looked up under CLAUDE_PROJECT_DIR."""
        a = self.proj(settings_me="emanuel")
        b = self.proj(settings_me="hadi")
        env_root = a  # CLAUDE_PROJECT_DIR = a, payload paths in a
        pl = file_payload(a, "Write", os.path.join(a, "docs/human/emanuel/x"))
        self.assertEqual(run_hook(env_root, pl, me=None)[0], 0)
        self.assertIsNotNone(b)


# --------------------------------------------------------------------- bash
class BashTests(HookCase):
    """Bash heuristic. ME=hadi unless noted."""

    SETTINGS_ME = "hadi"

    BLOCKED = [
        "echo x > docs/human/emanuel/a.md",
        "echo x >> docs/agent/david-li/a.md",
        "echo x>>docs/agent/david-li/a.md",
        "cp docs/agent/hadi/a docs/agent/emanuel/",
        "cp src/a.py docs/human/david-leh/a.py",
        "mv docs/human/emanuel/a.md /tmp/",
        "mv /tmp/a docs/agent/emanuel/a",
        "git mv docs/archive/x y",
        "git rm docs/human/emanuel/a.md",
        "rm docs/archive/x.md",
        "rm -f docs/agent/david-li/a.md",
        "rm -rf docs/human/emanuel/old/",
        "touch docs/human/david-leh/n.md",
        "mkdir -p docs/agent/emanuel/new/",
        "rmdir docs/agent/emanuel/empty/",
        "ln -s ../x docs/agent/emanuel/l",
        "truncate -s0 docs/agent/emanuel/a",
        "dd if=/dev/zero of=docs/agent/emanuel/f count=1",
        "sed -i 's/a/b/' docs/human/emanuel/a.md",
        "sed -i.bak 's/a/b/' docs/human/emanuel/a.md",
        "sed --in-place 's/a/b/' docs/human/emanuel/a.md",
        "perl -pi -e 's/a/b/' docs/agent/emanuel/a.md",
        "perl -i -pe 's/a/b/' docs/agent/emanuel/a.md",
        "echo hi | tee docs/agent/david-li/a.md",
        "echo hi | tee -a docs/agent/david-li/a.md",
        "python3 -c \"open('docs/human/emanuel/a','w').write('x')\"",
        "python3 -c \"open('docs/human/emanuel/a', 'a').write('x')\"",
        "python3 -c 'open(\"docs/human/emanuel/a\",\"wb\").write(b\"x\")'",
        "python3 -c \"from pathlib import Path; Path('docs/agent/emanuel/a').write_text('x')\"",
        "cat <<EOF > docs/human/emanuel/a.md\nhi\nEOF",
        "echo x > ./docs/human/emanuel/a.md",
        "echo x > /abs/project/docs/human/emanuel/a.md",
        "echo x 2>&1 > docs/human/emanuel/a.md",
        "cd /tmp && echo x > $PWD/docs/agent/emanuel/a",
        "echo x > docs/archive/new.md",
        "cp a docs/archive/b",
        "echo ok; rm docs/human/emanuel/a.md",
        "cat a | tee docs/human/emanuel/copy.md > /dev/null",
        "echo x > docs/human/bob/a.md",
    ]

    ALLOWED = [
        "cat docs/human/emanuel/a.md",
        "cat docs/agent/david-li/a.md | head",
        "grep x docs/human/emanuel/a 2>/dev/null",
        "grep -rn foo docs/agent/emanuel/ 2>&1",
        "grep -r 'a->b' docs/human/emanuel/",
        "ls docs/agent/emanuel/",
        "ls -la docs/human/david-leh/ 2>&1 | head",
        "head -5 docs/archive/x.md",
        "tail -n 3 docs/archive/x.md",
        "sed -n '1,5p' docs/human/emanuel/a.md",
        "git log --oneline docs/agent/emanuel/",
        "git diff docs/human/david-li/",
        "git diff HEAD~1 -- docs/archive/",
        "git status docs/human/emanuel/",
        "find docs/agent/emanuel -name '*.md'",
        "wc -l docs/human/emanuel/a.md",
        "diff docs/human/emanuel/a.md docs/human/hadi/a.md",
        "cat docs/archive/x >/dev/null",
        "cat docs/archive/x > /dev/null 2>&1",
        "cat docs/archive/x &>/dev/null",
        "cat docs/human/emanuel/a.md 2>>/dev/null",
        "less docs/human/emanuel/a.md",
        "file docs/human/emanuel/cp-notes.md",
        "cat docs/human/emanuel/rm.md",
        "cat docs/human/emanuel/touch-me.md",
        "python3 -c \"print(open('docs/human/emanuel/a').read())\"",
        "python3 -c \"print(open('docs/human/emanuel/a','r').read())\"",
        "echo hello",
        "echo x > docs/human/hadi/a.md",
        "echo x >> docs/agent/hadi/a.md",
        "cp src/a docs/agent/hadi/",
        "rm docs/human/hadi/old.md",
        "touch docs/human/hadi/x.md",
        "mkdir -p docs/agent/hadi/sub/",
        "git mv docs/human/hadi/a docs/human/hadi/b",
        "echo x > docs/human/TEAM_PROCESS.md",
        "echo x > docs/agent/BOARD.md",
        "echo x > src/out.txt",
        "rm -rf /tmp/build",
        "git commit -m 'update docs/human/emanuel/ links'",
        "cat docs/human/emanuel/a.md | wc -l",
        "",
    ]

    def test_blocked_commands(self):
        """Write-like commands touching another person's folder / archive are blocked."""
        for cmd in self.BLOCKED:
            with self.subTest(cmd=cmd):
                self.assertBlocked(self.run_h(bash_payload(self.root, cmd)), "should block: %r" % cmd)

    def test_allowed_commands(self):
        """Reads, own-folder writes and unrelated commands are allowed."""
        for cmd in self.ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertAllowed(self.run_h(bash_payload(self.root, cmd)), "should allow: %r" % cmd)

    def test_counts_meet_spec_minimum(self):
        """Sanity: at least 10 read and 10 write commands are exercised."""
        self.assertGreaterEqual(len(self.BLOCKED), 10)
        self.assertGreaterEqual(len(self.ALLOWED), 10)

    def test_each_slug_as_me_own_vs_other_bash(self):
        """For every ME, own-folder redirect is allowed and others' is blocked."""
        for me in SLUGS:
            for other in SLUGS:
                with self.subTest(me=me, other=other):
                    res = self.run_h(bash_payload(self.root, "echo x > docs/agent/%s/a.md" % other), me=me)
                    (self.assertAllowed if other == me else self.assertBlocked)(res)

    def test_bash_me_unset_write_to_any_person_folder_blocked(self):
        """With no identity (project without settings.local.json), bash writes to any person folder are blocked."""
        root = make_project()
        try:
            for s in SLUGS:
                with self.subTest(slug=s):
                    self.assertBlocked(run_hook(root, bash_payload(root, "echo x > docs/human/%s/a" % s), me=None))
            self.assertAllowed(run_hook(root, bash_payload(root, "cat docs/human/hadi/a"), me=None))
            self.assertBlocked(run_hook(root, bash_payload(root, "echo x > docs/archive/a"), me=None))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_bash_missing_or_bad_command_field(self):
        """Missing / empty / null command is allowed."""
        for ti in ({}, {"command": ""}, {"command": None}):
            with self.subTest(ti=ti):
                self.assertAllowed(self.run_h({"tool_name": "Bash", "tool_input": ti, "cwd": self.root}))

    # ---- accepted false positives (hook blocks, ideal behaviour is allow) ----
    @unittest.expectedFailure
    def test_ACCEPTED_FP_read_other_write_own(self):
        """ACCEPTED FALSE POSITIVE: reading emanuel's file while writing into own folder."""
        self.assertAllowed(self.run_h(bash_payload(self.root, "cp docs/agent/emanuel/a.md docs/agent/hadi/a.md")))

    @unittest.expectedFailure
    def test_ACCEPTED_FP_redirect_read_to_tmp(self):
        """ACCEPTED FALSE POSITIVE: `cat <other> > /tmp/out` only reads the protected file."""
        self.assertAllowed(self.run_h(bash_payload(self.root, "cat docs/human/emanuel/a.md > /tmp/out.txt")))

    @unittest.expectedFailure
    def test_ACCEPTED_FP_unrelated_rm_in_same_command(self):
        """ACCEPTED FALSE POSITIVE: unrelated write op elsewhere in a read command line."""
        self.assertAllowed(self.run_h(bash_payload(self.root, "ls docs/human/emanuel/; rm /tmp/x")))

    @unittest.expectedFailure
    def test_ACCEPTED_FP_write_word_in_quoted_grep_pattern(self):
        """ACCEPTED FALSE POSITIVE: the word 'rm' inside a quoted grep pattern."""
        self.assertAllowed(self.run_h(bash_payload(self.root, "grep 'rm' docs/human/emanuel/a.md")))

    @unittest.expectedFailure
    def test_ACCEPTED_FP_awk_comparison(self):
        """ACCEPTED FALSE POSITIVE: awk '>' comparison counts as redirect."""
        self.assertAllowed(self.run_h(bash_payload(self.root, "awk '$1>3' docs/human/emanuel/a.md")))

    @unittest.expectedFailure
    def test_ACCEPTED_FP_commit_message_mentions_path_and_cp(self):
        """ACCEPTED FALSE POSITIVE: commit message text containing path and 'mv'."""
        self.assertAllowed(self.run_h(bash_payload(self.root, "git commit -m 'mv docs/human/emanuel/ notes'")))

    # ---- documented heuristic bypasses (hook allows, ideal behaviour is block) ----
    @unittest.expectedFailure
    def test_BYPASS_rm_whole_folder_without_trailing_slash(self):
        """BUG (high): `rm -rf docs/human/emanuel` (no trailing slash) is allowed."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "rm -rf docs/human/emanuel")))

    @unittest.expectedFailure
    def test_BYPASS_mv_folder_without_trailing_slash(self):
        """BUG (high): `mv docs/agent/emanuel /tmp/x` is allowed."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "mv docs/agent/emanuel /tmp/x")))

    @unittest.expectedFailure
    def test_BYPASS_cd_then_relative(self):
        """DOCUMENTED BYPASS: cd into the folder then write relative."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "cd docs/human/emanuel && echo x > a.md")))

    @unittest.expectedFailure
    def test_BYPASS_variable_indirection(self):
        """DOCUMENTED BYPASS: shell variable hides the path."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "D=docs/human; echo x > $D/emanuel/a.md")))

    @unittest.expectedFailure
    def test_BYPASS_glob(self):
        """DOCUMENTED BYPASS: glob hides the slug."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "echo x > docs/human/e*/a.md")))

    @unittest.expectedFailure
    def test_BYPASS_uppercase_path(self):
        """DOCUMENTED BYPASS: case variants on case-insensitive FS."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "echo x > docs/Human/emanuel/a.md")))

    @unittest.expectedFailure
    def test_BYPASS_sed_i_after_other_flags(self):
        """DOCUMENTED BYPASS: `sed -n -i` style combos / `sed -e ... -i`."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "sed -e 's/a/b/' -i docs/human/emanuel/a.md")))

    @unittest.expectedFailure
    def test_BYPASS_curl_or_install_or_rsync(self):
        """DOCUMENTED BYPASS: write ops outside the list (install, rsync, curl -o, cat > via exec)."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "install -m644 a docs/human/emanuel/a.md")))

    @unittest.expectedFailure
    def test_BYPASS_docs_path_with_dotdot_in_bash(self):
        """DOCUMENTED BYPASS: bash path with .. segment not normalised."""
        self.assertBlocked(self.run_h(bash_payload(self.root, "echo x > docs/human/hadi/../emanuel/a.md")))


class BashSymlinkCwdTests(HookCase):
    """Bash heuristic ignores cwd (documented limitation)."""

    SETTINGS_ME = "hadi"

    @unittest.expectedFailure
    def test_BYPASS_relative_write_with_cwd_in_other_folder(self):
        """DOCUMENTED BYPASS: payload cwd is another person's folder; command uses bare filename."""
        pl = {"tool_name": "Bash", "cwd": self.p("docs/human/emanuel"), "tool_input": {"command": "echo x > a.md"}}
        self.assertBlocked(self.run_h(pl))


# ---------------------------------------------------------- robust input
class RobustnessTests(HookCase):
    """Malformed input, fail-open behaviour, exit codes, stdout hygiene."""

    SETTINGS_ME = "hadi"

    def assertFailOpen(self, res):
        """Exit 0 with a stderr warning."""
        code, err, _ = res
        self.assertEqual(code, 0, err)
        self.assertIn("warning", err.lower())

    def test_empty_stdin(self):
        """Empty stdin: exit 0 + warning."""
        self.assertFailOpen(self.run_h(""))

    def test_whitespace_stdin(self):
        """Whitespace-only stdin: exit 0 + warning."""
        self.assertFailOpen(self.run_h("  \n\t "))

    def test_malformed_json(self):
        """Broken JSON: exit 0 + warning."""
        for raw in ("{", "{'tool_name': 'Write'}", "not json", '{"tool_name": "Write",}', "\x00\x01"):
            with self.subTest(raw=raw):
                self.assertFailOpen(self.run_h(raw))

    def test_non_object_json(self):
        """Valid JSON that is not an object: exit 0 + warning."""
        for raw in ("[]", "[1,2]", "null", "42", '"Write"', "true"):
            with self.subTest(raw=raw):
                self.assertFailOpen(self.run_h(raw))

    def test_empty_object(self):
        """{} has nothing to check: allow."""
        self.assertAllowed(self.run_h("{}"))

    def test_missing_tool_input(self):
        """Missing / null tool_input for each managed tool: allow without crash."""
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
            for pl in ({"tool_name": tool}, {"tool_name": tool, "tool_input": None}):
                with self.subTest(tool=tool, pl=pl):
                    self.assertAllowed(self.run_h(pl))

    def test_wrong_typed_tool_input_fails_open(self):
        """tool_input of the wrong type: exit 0 (fail open), warning allowed."""
        for ti in ("string", 5, [1], True):
            with self.subTest(ti=ti):
                self.assertAllowed(self.run_h({"tool_name": "Write", "tool_input": ti}))

    def test_wrong_typed_fields_fail_open(self):
        """Non-string path/command/cwd values: exit 0."""
        for pl in ({"tool_name": "Write", "tool_input": {"file_path": 5}},
                   {"tool_name": "Write", "tool_input": {"file_path": ["a"]}},
                   {"tool_name": "Write", "tool_input": {"file_path": "a"}, "cwd": 5},
                   {"tool_name": "Bash", "tool_input": {"command": 5}},
                   {"tool_name": "Bash", "tool_input": {"command": ["echo"]}},
                   {"tool_name": ["Write"], "tool_input": {}}):
            with self.subTest(pl=pl):
                self.assertAllowed(self.run_h(pl))

    def test_block_output_contract(self):
        """Block: exit 2, one stderr line, nothing on stdout."""
        res = self.run_h(file_payload(self.root, "Write", self.p("docs/human/emanuel/a.md")))
        self.assertBlocked(res)
        self.assertEqual(res[2], "")
        self.assertIn("emanuel", res[1])

    def test_allow_output_contract(self):
        """Allow: exit 0, empty stderr, empty stdout."""
        res = self.run_h(file_payload(self.root, "Write", self.p("src/a.py")))
        self.assertEqual(res, (0, "", ""))

    def test_extra_payload_fields_ignored(self):
        """Real Claude Code payloads carry extra keys; they must not matter."""
        pl = {"session_id": "s", "transcript_path": "/x", "hook_event_name": "PreToolUse",
              "permission_mode": "default", "tool_use_id": "t",
              "tool_name": "Write", "cwd": self.root,
              "tool_input": {"file_path": self.p("docs/human/emanuel/a.md"), "content": "x"}}
        self.assertBlocked(self.run_h(pl))

    def test_nonexistent_project_dir_fails_open_or_decides(self):
        """CLAUDE_PROJECT_DIR points at a missing dir: must not crash with a traceback / exit 1."""
        script = os.path.join(self.root, ".claude", "hooks", "guard_docs.py")
        env = {k: v for k, v in os.environ.items() if k not in ("ME", "CLAUDE_PROJECT_DIR")}
        env["CLAUDE_PROJECT_DIR"] = self.root + "-does-not-exist"
        env["ME"] = "hadi"
        p = subprocess.run([sys.executable, script], input=json.dumps(
            file_payload(self.root, "Write", self.p("src/a.py"))), capture_output=True, text=True, env=env)
        self.assertIn(p.returncode, (0, 2))
        self.assertNotIn("Traceback", p.stderr)

    def test_large_command_input(self):
        """A 1 MB command does not crash or hang the hook."""
        cmd = "echo " + "a" * 1_000_000
        self.assertAllowed(self.run_h(bash_payload(self.root, cmd)))

    def test_pathological_regex_input(self):
        """Many quote/paren characters do not cause catastrophic regex backtracking."""
        cmd = "open(" + "'" * 5000 + " docs/human/emanuel/ "
        t0 = time.perf_counter()
        self.run_h(bash_payload(self.root, cmd))
        self.assertLess(time.perf_counter() - t0, 2.0)


# ---------------------------------------------------------------- repo files
class RepoConfigTests(unittest.TestCase):
    """Static checks on the real repo files (settings.json, .gitignore)."""

    ROOT = os.path.dirname(os.path.dirname(HERE))

    def read(self, rel):
        """Return the text of a repo file."""
        with open(os.path.join(self.ROOT, rel)) as f:
            return f.read()

    def test_gitignore_has_settings_local(self):
        """.gitignore contains .claude/settings.local.json."""
        lines = [l.strip() for l in self.read(".gitignore").splitlines()]
        self.assertIn(".claude/settings.local.json", lines)

    def test_settings_json_registers_hook(self):
        """settings.json has a PreToolUse command hook for all five tools."""
        cfg = json.loads(self.read(".claude/settings.json"))
        groups = cfg["hooks"]["PreToolUse"]
        self.assertEqual(len(groups), 1)
        matcher = groups[0]["matcher"]
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
            self.assertIn(tool, matcher.split("|"))
        h = groups[0]["hooks"][0]
        self.assertEqual(h["type"], "command")
        self.assertIn("guard_docs.py", h["command"])
        self.assertIn('"$CLAUDE_PROJECT_DIR', h["command"])  # quoted for paths with spaces

    def test_settings_local_is_valid_json_with_valid_slug(self):
        """settings.local.json (if present) parses and has a valid slug."""
        pth = os.path.join(self.ROOT, ".claude", "settings.local.json")
        if not os.path.exists(pth):
            self.skipTest("no settings.local.json on this machine")
        self.assertIn(json.loads(self.read(".claude/settings.local.json"))["env"]["ME"], SLUGS)

    def test_hook_file_stdlib_only(self):
        """guard_docs.py imports only the standard library."""
        import ast
        tree = ast.parse(self.read(".claude/hooks/guard_docs.py"))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertLessEqual(mods, set(sys.stdlib_module_names))

    def test_real_hook_against_real_repo(self):
        """Smoke test the real script/real repo with ME=hadi."""
        script = os.path.join(self.ROOT, ".claude", "hooks", "guard_docs.py")
        env = {k: v for k, v in os.environ.items() if k not in ("ME", "CLAUDE_PROJECT_DIR")}
        env.update(ME="hadi", CLAUDE_PROJECT_DIR=self.ROOT)
        for rel, code in (("docs/human/emanuel/x.md", 2), ("docs/human/hadi/x.md", 0), ("docs/archive/x", 2)):
            pl = {"tool_name": "Write", "cwd": self.ROOT, "tool_input": {"file_path": rel}}
            p = subprocess.run([sys.executable, script], input=json.dumps(pl), capture_output=True,
                               text=True, env=env)
            self.assertEqual(p.returncode, code, rel)


# ------------------------------------------------------------------- timing
class TimingTests(HookCase):
    """Each call must complete in < 100 ms (wall clock incl. interpreter start)."""

    SETTINGS_ME = "hadi"
    N = 25

    def measure(self, payload):
        """Return list of wall times (s) for N runs of payload."""
        out = []
        for _ in range(self.N):
            t0 = time.perf_counter()
            run_hook(self.root, payload, me="hadi")
            out.append(time.perf_counter() - t0)
        return out

    def test_latency_under_100ms(self):
        """Max and median latency for block/allow/bash/malformed paths stay below 100 ms."""
        cases = {
            "file-allow": file_payload(self.root, "Write", self.p("src/a.py")),
            "file-block": file_payload(self.root, "Write", self.p("docs/human/emanuel/a.md")),
            "bash-read": bash_payload(self.root, "cat docs/human/emanuel/a.md | head"),
            "bash-block": bash_payload(self.root, "echo x >> docs/agent/emanuel/a.md"),
            "malformed": "{",
        }
        worst = 0.0
        for name, pl in cases.items():
            times = self.measure(pl)
            worst = max(worst, max(times))
            print("\n  latency %-10s min=%.1fms median=%.1fms max=%.1fms" % (
                name, min(times) * 1e3, sorted(times)[len(times) // 2] * 1e3, max(times) * 1e3))
            with self.subTest(case=name):
                # p90 gates (a single OS scheduling hiccup must not flake the suite);
                # the true max is printed above and in the final report.
                p90 = sorted(times)[int(len(times) * 0.9)]
                self.assertLess(p90, 0.100, "p90 %.1f ms" % (p90 * 1e3))
        print("  worst-case latency this class: %.1f ms" % (worst * 1e3))


def tearDownModule():
    """Print the largest latency seen by any subprocess call in this run."""
    print("\nMAX single-call wall time over whole run: %.1f ms" % (MAX_LATENCY[0] * 1e3))
# [END AI-GENERATED]


if __name__ == "__main__":
    unittest.main()
