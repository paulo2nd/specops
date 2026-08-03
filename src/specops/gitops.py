"""Git access layer — the single site that invokes ``git`` (Feature 020).

Every git operation runs through ``git`` plumbing subprocesses; no third-party
git library is imported. The output shape matches the previous GitPython
implementation byte-for-byte: git's own output is passed through with the same
default quoting (non-ASCII paths stay C-quoted, e.g. ``"caf\\303\\251.txt"``),
and callers strip/splitlines exactly as before, so the trailing newline git emits
(which GitPython stripped) makes no observable difference.

Ledger-domain sentinels (the ``(human)`` commit marker) are filtered by callers,
never here (Feature 019 US4, FR-009/FR-011).
"""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from specops.errors import SpecopsError

GIT_UNAVAILABLE_MSG = (
    "git executable not found or not functional on PATH. "
    "Install Git and ensure `git` is on your PATH."
)


class GitError(SpecopsError):
    """A ``git`` invocation failed (or git is unavailable). Exit code 1.

    A ``SpecopsError`` so an uncaught instance is reported cleanly by the CLI
    error boundary (exit 1) rather than as a traceback. Read helpers that today
    degrade on git errors (returning ``[]``/``None``/``False``) keep doing so;
    ``GitError`` is raised only where the previous code raised
    ``git.exc.GitCommandError`` (callers own the degradation)."""


@dataclass(frozen=True)
class Repository:
    """A resolved git repository — the SpecOps-owned handle replacing ``git.Repo``.

    ``root`` is where git commands run (``git -C root``). ``working_tree_dir`` is
    the working-tree root, or ``None`` for a bare repository (matching
    GitPython's ``Repo.working_tree_dir`` so callers' bare-repo handling is
    unchanged). For a normal repository the two are equal.
    """

    root: Path
    working_tree_dir: Path | None


# ---------------------------------------------------------------------------
# Invocation (contracts/git-invocation.md)
# ---------------------------------------------------------------------------


def _spawn(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git argv, capturing text; never raises on non-zero exit.

    Decodes as UTF-8 with ``surrogateescape`` (faithful to any non-decodable
    bytes). A missing/nonfunctional git binary raises :class:`GitError` — the
    single fail-closed precondition (FR-012). No shell, no interpolation. The one
    place a git subprocess is spawned, so the env/decode/unavailability handling
    has exactly one definition."""
    try:
        return subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="surrogateescape",
        )
    except (FileNotFoundError, OSError) as exc:
        raise GitError(GIT_UNAVAILABLE_MSG) from exc


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``git -C root <args>`` capturing text output; never raises on non-zero."""
    return _spawn(["git", "-C", str(root), *args])


def _run_ok(root: Path, args: list[str]) -> str:
    """Run git; raise :class:`GitError` on non-zero exit. Return stdout verbatim."""
    proc = _git(root, args)
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def ensure_git_available() -> str:
    """Verify a functional ``git`` on PATH; return its version string (FR-012).

    "Present & functional": probe ``git --version``. Raises :class:`GitError`
    with a clear diagnostic when git is absent or nonfunctional. No minimum
    version is enforced — every plumbing invocation used predates git ~1.8. The
    single shared precondition, consumed by ``specops init`` (first step) and
    ``specops doctor``."""
    proc = _spawn(["git", "--version"])
    if proc.returncode != 0:
        raise GitError(GIT_UNAVAILABLE_MSG)
    return proc.stdout.strip()


# ---------------------------------------------------------------------------
# Repository resolution
# ---------------------------------------------------------------------------


def find_repo(path: Path = Path(".")) -> Repository | None:
    """Return the :class:`Repository` for *path*, or None if not inside one.

    Searches parent directories (git's own default), matching the previous
    ``search_parent_directories=True``. The normal-worktree hot path is a single
    ``git`` invocation. ``--show-toplevel`` fails for a bare repository *or* a
    worktree-less ``GIT_DIR`` context (e.g. cwd inside ``.git``); both resolve to
    the git dir with ``working_tree_dir=None`` — matching GitPython's
    ``working_tree_dir`` there, so callers' bare-repo guards still fire instead of
    silently running against the git directory."""
    top = _git(path, ["rev-parse", "--show-toplevel"])
    if top.returncode == 0 and top.stdout.strip():
        wt = Path(top.stdout.strip())
        return Repository(root=wt, working_tree_dir=wt)
    gitdir = _git(path, ["rev-parse", "--git-dir"])
    if gitdir.returncode != 0:
        return None  # not a git repository at all
    raw = gitdir.stdout.strip()
    root = Path(raw) if Path(raw).is_absolute() else (Path(path) / raw).resolve()
    return Repository(root=root, working_tree_dir=None)


def is_git_repo(path: Path = Path(".")) -> bool:
    return find_repo(path) is not None


def git_dir(repo: Repository) -> Path:
    """Return the absolute git directory for *repo* (``git rev-parse --git-dir``).

    For a normal repository this is ``<root>/.git``; for a linked worktree it is the
    worktree's own git dir. Used to place ephemeral, never-committed local state (the
    gate-run cache, Feature 024) outside the working tree — so it never shows in
    ``git status``/``git diff`` and cannot dirty the tree."""
    raw = _run_ok(repo.root, ["rev-parse", "--git-dir"]).strip()
    p = Path(raw)
    return p if p.is_absolute() else (repo.root / p).resolve()


# ---------------------------------------------------------------------------
# Refs, commits, ancestry
# ---------------------------------------------------------------------------


def current_branch(repo: Repository) -> str:
    """The current branch name, or a 7-char short SHA when HEAD is detached."""
    proc = _git(repo.root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return head_sha(repo)[:7]


def head_sha(repo: Repository) -> str:
    return _run_ok(repo.root, ["rev-parse", "HEAD"]).strip()


def commits_in_range(repo: Repository, start_sha: str, end_sha: str = "HEAD") -> list[str]:
    """Return commit shas in *start_sha..end_sha* (exclusive start, inclusive end).

    An unresolvable *start_sha* degrades to ``[]`` (as before); an unresolvable
    *end_sha* raises :class:`GitError` — the previous GitPython path guarded only
    the start and let a bad end propagate, so this preserves that contract."""
    if not commit_exists(repo, start_sha):
        return []
    return [
        line for line in _run_ok(repo.root, ["rev-list", f"{start_sha}..{end_sha}"]).splitlines()
        if line
    ]


def is_ancestor(repo: Repository, sha: str) -> bool:
    """Return True when *sha* is reachable from HEAD (i.e. an ancestor).

    A pure git ancestry predicate: ledger-domain sentinels (the human-work
    commit marker) are filtered by callers via ``ledger.is_human_commit`` —
    this generic layer knows nothing about them (Feature 019 US4, FR-009)."""
    return _git(repo.root, ["merge-base", "--is-ancestor", sha, "HEAD"]).returncode == 0


def merge_base(repo: Repository, ref: str, other: str = "HEAD") -> str | None:
    """Return the best common ancestor sha of *ref* and *other*, or None.

    None when either side is unresolvable (an absent candidate ref, an unborn
    HEAD) or there is no common ancestor — the degradation the baseline
    fallback in ``trace`` relies on."""
    proc = _git(repo.root, ["merge-base", ref, other])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def symbolic_ref(repo: Repository, name: str) -> str | None:
    """Resolve a symbolic ref to its short target (e.g. ``origin/main``), or None."""
    proc = _git(repo.root, ["symbolic-ref", "--quiet", "--short", name])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def commit_exists(repo: Repository, sha: str) -> bool:
    """Return True when *sha* resolves to a commit in this clone."""
    return _git(
        repo.root, ["rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"]
    ).returncode == 0


def resolve_commit(repo: Repository, rev: str) -> str | None:
    """Resolve *rev* (short sha, ref, …) to its full 40-char commit sha, or None.

    The sha-returning companion to :func:`commit_exists`: callers that must
    persist a canonical, unambiguous commit id (e.g. ``trace link`` writing into
    ``tasks[].commits``) resolve here so a user-supplied abbreviation is stored in
    the same full form ``complete-task`` harvests."""
    proc = _git(repo.root, ["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def blob_sha(repo: Repository, rev: str, path: str) -> str | None:
    """Return the git blob SHA of *path* at *rev*, or None when it does not resolve.

    A deterministic, offline, per-path content digest (git's own object hash): two
    revisions with byte-identical content at *path* share a blob SHA, so a change to
    any other path leaves it unchanged (Feature 015 per-path staleness). Returns
    None when *rev* is unresolvable or *path* is absent (a removed/renamed path),
    which the caller treats as stale."""
    proc = _git(repo.root, ["rev-parse", "--verify", "--quiet", f"{rev}:{path}"])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


# ---------------------------------------------------------------------------
# Working tree: status, tracked files, diffs
# ---------------------------------------------------------------------------


def dirty_files(repo: Repository) -> list[str]:
    """Return `git status --porcelain` lines; empty list means a clean tree."""
    out = _run_ok(repo.root, ["status", "--porcelain"])
    return [line for line in out.splitlines() if line.strip()]


def porcelain_status(repo: Repository, *, untracked_all: bool = False) -> list[str]:
    """Return raw `git status --porcelain` lines (``-uall`` expands untracked dirs).

    Blank-line filtering is left to the caller (the lane parses column offsets)."""
    args = ["status", "--porcelain"]
    if untracked_all:
        args.append("-uall")
    return _run_ok(repo.root, args).splitlines()


def worktree_digest(repo: Repository) -> str:
    """Return ``sha256:<hex>`` of the *uncommitted* working-tree state (Feature 024).

    Combines ``git diff HEAD`` (all tracked, un/staged modifications relative to HEAD)
    with the ``-uall`` porcelain listing **and the content of each untracked file** — so
    editing a newly-added file without ``git add`` still changes the digest. Deterministic
    for identical tree state; a clean tree yields a stable digest of the empty diff + empty
    status. Content inside the git directory (e.g. the gate-run cache) never appears, so the
    digest is not perturbed by the cache it guards.

    **Limitation**: gitignored paths are invisible to git (they appear in neither
    ``git diff`` nor porcelain), so a gate whose command reads *mutable gitignored* state
    (e.g. a local ``.env`` fixture) is not covered — its change will not invalidate the
    cache. Such inputs are outside git's (and SpecOps's) view by construction."""
    h = hashlib.sha256()
    h.update(_git(repo.root, ["diff", "HEAD"]).stdout.encode("utf-8", "surrogateescape"))
    for line in sorted(porcelain_status(repo, untracked_all=True)):
        h.update(b"\0")
        h.update(line.encode("utf-8", "surrogateescape"))
        # Untracked entries (`?? path`) contribute their content, not just their name.
        if line.startswith("?? "):
            try:
                content = (repo.root / line[3:]).read_bytes()
            except OSError:
                content = b""
            h.update(b"\0")
            h.update(content)
    return "sha256:" + h.hexdigest()


def ls_files(repo: Repository) -> list[str]:
    """Return the tracked files (`git ls-files`); empty list when none."""
    return [f for f in _run_ok(repo.root, ["ls-files"]).splitlines() if f]


def is_tracked(repo: Repository, path: str) -> bool:
    """Return True when *path* is tracked in the index (`ls-files --error-unmatch`)."""
    return _git(repo.root, ["ls-files", "--error-unmatch", path]).returncode == 0


def name_only_diff(repo: Repository, start_sha: str, end_sha: str = "HEAD") -> list[str]:
    """Return deduplicated list of changed file paths between *start_sha* and *end_sha*."""
    proc = _git(repo.root, ["diff", "--name-only", start_sha, end_sha])
    if proc.returncode != 0:
        return []
    return [f for f in proc.stdout.splitlines() if f]


def parse_name_status(raw: str) -> list[tuple[str, str]]:
    """Parse ``git diff --name-status`` output into ``(status, path)`` pairs.

    The single parse loop (Feature 019 US4, FR-008): ``status`` is the first
    letter of the code (``R100`` → ``R``), ``path`` the last tab field — the NEW
    path for a rename line. Blank lines are skipped.
    """
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        out.append((parts[0][:1], parts[-1]))
    return out


def name_status_diff(
    repo: Repository, start_sha: str | None, end_sha: str = "HEAD", *,
    rename_aware: bool, cached: bool = False,
) -> list[tuple[str, str]]:
    """The single ``--name-status`` invocation, rename-awareness as a parameter
    (Feature 019 US4, FR-008).

    ``rename_aware=False`` → ``--no-renames``: a rename **decomposes** into a
    removed old path plus an added new path (no similarity threshold).
    ``rename_aware=True`` → ``-M``: a rename is a single ``R`` on the NEW path
    (an ordinary file move is not mis-flagged destructive — lane safety).
    ``cached=True`` diffs the index (staged changes; the commit range is
    ignored). A ``None`` *start_sha* (non-cached) is omitted so git diffs
    ``end_sha`` against the working tree — matching GitPython, which dropped the
    ``None`` arg (never diffed against an empty ``""`` revision). Raises
    :class:`GitError` — each caller owns its degradation policy
    (``effective_diff_status`` returns ``[]``; lane suppresses).
    """
    flag = "-M" if rename_aware else "--no-renames"
    if cached:
        args = ["diff", "--cached", "--name-status", flag]
    else:
        range_args = [a for a in (start_sha, end_sha) if a]
        args = ["diff", "--name-status", flag, *range_args]
    return parse_name_status(_run_ok(repo.root, args))


def effective_diff_status(
    repo: Repository, start_sha: str, end_sha: str = "HEAD"
) -> list[tuple[str, str]]:
    """Return `(status, path)` pairs between *start_sha* and *end_sha* (Feature 010, R1).

    The rename-decomposed projection of :func:`name_status_diff` (same name,
    signature, and ``[]``-on-error semantics as always). Mode-only changes are
    still listed; symlinks appear by their own path entry and are not followed
    (``git diff`` never dereferences them). ``status`` is Git's single-letter
    code (``A``/``M``/``D``/…).
    """
    try:
        return name_status_diff(repo, start_sha, end_sha, rename_aware=False)
    except GitError:
        return []


def effective_diff(repo: Repository, start_sha: str, end_sha: str = "HEAD") -> list[str]:
    """Return the deterministic, codepoint-sorted effective-diff paths (name-only).

    A thin projection of :func:`effective_diff_status` so the diff invocation lives
    in exactly one place.
    """
    return sorted({p for _status, p in effective_diff_status(repo, start_sha, end_sha)})
