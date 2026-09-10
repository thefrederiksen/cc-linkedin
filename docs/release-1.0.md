# cc-linkedin 1.0.0 - the packaging release

Status: BUILT AND PROVEN on branch `release-1.0`, cut from `origin/main` at
`e886a38`. Not tagged - the Architect tags after this lands.

Scope, as briefed: make it pip-installable and release 1.0.0. No new verbs, no
refactoring beyond what packaging needed. One code correction was folded in on
the Architect's instruction and is described below.

---

## The constraint that outranked everything

The owner's video pipeline posts to LinkedIn every morning through a shim
OUTSIDE this repository at `%LOCALAPPDATA%/cc-director/bin/cc-linkedin.cmd`:

```
@echo off
py -3.11 "D:\ReposFred\cc-linkedin\cc_linkedin.py" %*
```

`D:/ReposFred/cc-consult/tools/cc-linkedin/post.py` drives it, and it invokes
the FILE with `sys.executable`, not the console script. If that path breaks, the
morning post fails and nobody finds out until it has not appeared.

So `cc_linkedin.py` stays a directly runnable file at the repository root. It
was not moved and was not turned into a stub that needs an install. `pyproject.toml`
carries that reasoning as a comment next to the setting it constrains, where
somebody tidying the layout will actually read it.

**It was proven by RUNNING it, not by reasoning about imports.** See proof 4.

---

## What changed

| | |
|---|---|
| `kit/` renamed to `cc_linkedin_kit/` | `git mv`, so all eleven modules keep their history |
| `pyproject.toml` | setuptools, `requires-python >=3.11`, version `1.0.0` in ONE place |
| `MANIFEST.in` | prunes `docs/`, `tests/`, `tools/` from the source distribution |
| `.gitignore` | build artefacts |
| `cc_linkedin_kit/browser.py` | `surface_kind` corrected - see below |
| `README.md` | Install, all 18 commands, and what is NOT in 1.0 |
| `.claude/skills/linkedin/SKILL.md` | brought current with every verb that exists today |

Console script: `cc-linkedin = cc_linkedin:main`.
Dependency: `playwright>=1.58` - a floor actually run, not guessed. 1.58.0 is the
interpreter this was developed against; a fresh resolve installs 1.62.0. Both
were exercised.

### Why `kit` had to be renamed

`kit` is far too generic to install into somebody's `site-packages`. Installed,
it claims the top-level name `kit` for every other package on the machine.

The rename surface was MEASURED before it was touched, not assumed:

* **Seven** absolute `kit` imports exist in shipped code, all in `cc_linkedin.py`
  - one at module level, six inside `main()` ABOVE `parse_args`. Any invocation
  at all, `--help` included, executes all seven.
* **Twenty-four** imports inside the package are RELATIVE, which a package
  rename cannot touch.
* **Zero** uses of `importlib`, `__import__`, or any string-named module lookup
  in shipped code.

The literal string `kit` was then swept out of every tracked file of EVERY type,
not only the Python ones - a batch file or a path built from a string is the
shape that breaks quietly and that the test suite would not catch. The sweep
found three live references (a code comment, a README line, a test comment) and
one glob pattern in `tests/test_no_leak.py`. All fixed. No `.cmd` file, no
packaging metadata and no string-built path referenced it.

`docs/evidence/` and the inspection reports still say `kit`, deliberately. They
cite it at specific past commits and are record, not code; rewriting them would
falsify the evidence they exist to hold.

### The `surface_kind` correction

Folded in on the Architect's instruction. A2 (landed in #8) asked "is this
surface mine" and got two cases the wrong way round: it uncapped `/messaging/`
because the inbox is the owner's, while `/messaging/compose/` - measured to open
no conversation - stayed capped by not being matched. But the LIST is the route
believed to select a conversation into the reading pane, and that marks it read.

**The rule is not "is this surface mine". It is "can loading it change something
another person can see."** A read receipt is visible to somebody else. That
sentence is now the docstring's rule, with the cases below it as where it has
been applied so far.

| Surface | 1.0 | was |
|---|---|---|
| `/messaging/` | CAPPED | uncapped |
| `/messaging/compose/` | UNCAPPED, matched exactly not as a prefix | capped |
| `/messaging/thread/<id>/` | CAPPED | unchanged |
| `/mynetwork/invitation-manager/` | UNCAPPED | unchanged |

Watched failing first: the corrected test was written against the shipped
classifier and produced **seven failures in exactly the two directions above**,
then the fix, then 24 green.

No verb in 1.0 loads `/messaging/`, so there was no behaviour to re-prove. This
was a safety classification wrong in the UNSAFE direction.

---

## The proofs

### 1. The file still runs directly - PASS

```
py -3.11 D:/ReposFred/cc-linkedin.release/cc_linkedin.py --help     exit 0, 19 subcommands
```

### 2. Editable install, console script - PASS

`pip install -e .` into a scratch venv, then `cc-linkedin --help` run **from a
directory that is not the repository**, so a leftover working-directory import
cannot mask a packaging fault. Exit 0.

### 3. Clean venv from a built wheel - PASS

A second, untouched venv installed from `cc_linkedin-1.0.0-py3-none-any.whl`,
console script again run from outside the repository. Exit 0, and
`cc_linkedin.__file__` resolves to `site-packages`, proving it is the installed
copy and not the repository one.

Artefact contents were inspected rather than assumed:

* wheel: `cc_linkedin.py` + the eleven `cc_linkedin_kit` modules + `dist-info`.
  **Zero** entries under `docs/`, `tests/` or `tools/`.
* sdist: same, plus README, requirements and pyproject. **Zero** `docs/surveys/`
  entries.

### 4. THE OWNER'S MORNING JOB - PASS

The proof that mattered most, and the only one an import assertion could not
give. Run in the exact shape `post.py` uses, invoked as the shim invokes it,
staged with no `--submit`:

```
py -3.11 <worktree>/cc_linkedin.py post --page 107519091 \
    --page-name "CenterConsulting, Inc." --text <temp file> --shot <png>
```

```
[08:26:51] composer open as CenterConsulting, Inc.
[08:26:51] composer is empty
[08:26:53] text verified: 297 chars, exact
[08:26:54] discarding composer (staged only, no --submit)
[08:26:54] Dismiss pressed
[08:26:54] Discard pressed
[08:26:54] composer discarded, nothing kept
RESULT staged file=- shot=...png seconds=10
```

Exit 0. Nothing was posted and nothing was left behind. The Page identity was
verified by the tool itself, and the text was read back character for character.

Cost: **zero capped views** - `pace.json` read 77/80 before and 77/80 after.

### 5. The rename, proven by PRESENCE in all three contexts - PASS

Stated as a presence and not an absence deliberately: "no ImportError was
raised" is an absence-shaped pass condition that certifies just as happily when
nothing was imported at all.

| context | loaded by `--help` | resolve when imported | loaded under `kit` |
|---|---|---|---|
| direct run (the shim's context) | 9 of 10 | **10 of 10** | none |
| editable venv | 9 of 10 | **10 of 10** | none |
| clean wheel venv | 9 of 10 | **10 of 10** | none |

### 6. The offline suite - PASS

262 passed before the rename, 262 after it, 265 after the classifier correction
added three cases.

---

## What is NOT proven, named honestly

**The full live selftest did not run.** It is the standing regression proof for
a change of this kind and it was substituted, with the Architect's approval,
because only 3 capped views remained for the day and the cap is never raised to
finish a run. The substitution rests on the measurement above: the rename
surface is seven absolute imports that any invocation executes, the rest are
relative, and there are no dynamic imports - so the live selftest would have
exercised BEHAVIOUR, which a rename does not change. That argument is sound for
a rename and would NOT be sound for a change that touched behaviour.

**I overstated the coverage of `--help` and the presence check caught it.** I
told the Architect that `--help` imports all ten modules. It imports nine:
`fixtures` is reached by a lazy relative import inside a function body in
`selftest.py`, so `--help` never walks it. The rename surface claim was still
correct - `fixtures` is reached RELATIVELY and a rename cannot break it - but
the module-coverage claim was wrong, and proof 5 imports all ten explicitly
rather than relying on what `--help` happens to touch.

**The offline suite proves the repository, not the installed package.** Every
test file does `sys.path.insert(0, <repo root>)`, so running it under a venv
python still imports the repository copy. Running it three times would have
produced three identical proofs of the same thing. The installed copies are
covered by proofs 2, 3 and 5 instead.

**`/messaging/` being capped is a decision, not a measurement.** Nobody has
measured whether loading the bare list actually opens a conversation. It is
capped because it is BELIEVED to, and the unsafe direction is the one that
costs. Uncapping it needs a measurement, not an argument.

**The wheel was not installed on another machine, or on non-Windows.** It is
pure-Python and platform-independent by construction, but that is reasoning, not
a test. The tool is Windows-only anyway - the native-dialog watchdog uses Win32.

**No licence is declared.** The repository has no LICENCE file and one was not
invented. That is the owner's call before this is ever published anywhere public
as a package.

---

## The verb count

Eighteen commands, plus `selftest`, taken off argparse rather than off memory.
The brief said seventeen; the measured number is eighteen and the Architect
accepted the correction.

| | |
|---|---|
| Posting (3) | `post`, `scheduled`, `unschedule` |
| Comments and reactions (8) | `read-post`, `read-comments`, `comment`, `reply`, `delete-comment`, `react`, `unreact`, `delete-post` |
| Reading and search (6) | `read-profile`, `read-company`, `search-people`, `search-posts`, `notifications`, `stats` |
| Invitations (1) | `withdraw` |

`selftest` is a development verb and is counted separately rather than padded
into the total.

## What is deliberately NOT in 1.0

Phase 3's seven remaining verbs are built on `phase-3-reach` but have never been
run against LinkedIn, and two of them send to real people. They stay out of a
release a stranger can install. The README and the skill both say these commands
DO NOT EXIST - not "coming soon", because a reader who thinks a verb is nearly
there plans around it.

* `connect`, `message`, `read-inbox`, `read-thread`, `invitations`, `follow`,
  `unfollow`, `invite-to-follow` - issue #9
* `post --profile`, `edit-post`, `repost` - issue #10

## Notes for whoever tags this

* The worktree is `D:/ReposFred/cc-linkedin.release`, NOT `.mission` - that
  directory was occupied by the live Phase 3 seat and was left alone.
* Nothing here tags or creates the GitHub release; that is the Architect's.
* After this merges, the shared checkout at `D:/ReposFred/cc-linkedin` needs a
  `git pull` before the next morning run, since the shim points at that path.
  The run will work either way - the shim runs the file, and the file works
  before and after - but the tree should not sit behind.
