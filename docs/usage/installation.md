# Installing Workstream Registration

This guide installs the `workstream-registration` CLI from source so you can register workspaces. It covers prerequisites, what actually gets installed (and where), verifying the install, reinstalling/upgrading, and uninstalling. All paths and behaviors below were verified on the tested profile (Windows, CPython 3.14.6, per-user global Python).

New to the tool? Start with the [quickstart](quickstart.md) after installing. For day-to-day operations see the [operator guide](guide.md); for commands, exit codes, and result envelopes see the [reference](reference.md); for how the pieces work see [how it works](how-it-works.md).

## Prerequisites

- **CPython 3.14.x.** The package requires `>=3.14,<3.15` and is pinned to the tested runtime 3.14.6. Verify: `python --version`.
- **git** (to clone and update the repository) — or any way to get a checkout of this repository on disk.
- **The repository checkout.** Installation is editable: the CLI runs from this checkout, so keep the clone on disk after installing.
- **pip** (bundled with CPython).

## Install

From the repository root, run:

```text
pip install -e .[dev]
```

This does three things:

1. Installs the package **editable** (`-e`): the installed package points at this checkout's `src/`, so code changes are picked up without reinstalling.
2. Installs the runtime dependency `jsonschema` (pinned `==4.26.0`).
3. Installs the **`dev` extra**: `pytest`. (Omit `.[dev]` if you do not want the test tooling — the CLI itself only needs the runtime dependency.)

The project also requires the stdlib `sqlite3` module (bundled with standard CPython builds) for the local projection; a build without it fails the conformance runner explicitly.

## What gets installed, and where

The install creates one console script — `workstream-registration` — plus the Python package. The script is defined in `pyproject.toml` (`[project.scripts]`) and pip places it in the **active environment's script directory**:

| Installation target | Script location | PATH behavior |
|---|---|---|
| Per-user global Python (Windows) | `<python>\Scripts\workstream-registration.exe` | The Scripts dir of a per-user Python is on PATH — callable from anywhere. |
| Virtual environment (venv) | `<venv>\Scripts\workstream-registration.exe` (Windows) / `<venv>\bin\workstream-registration` (POSIX) | On PATH **only while the venv is activated**. Deactivate or open a new shell and the command is gone. |
| System Python (POSIX, often) | `/usr/local/bin` or the system Python's `bin` | On PATH only when that directory is on PATH (may require the system package manager or `pip --user`). |

On the tested profile (per-user global Python 3.14.6 on Windows), the script was installed to:

```text
C:\Users\<you>\AppData\Local\Python\pythoncore-3.14-64\Scripts\workstream-registration.exe
```

That Scripts directory is on PATH, so the command works from any directory. Two consequences worth knowing:

- **Global install = one copy, everywhere.** Installing into the per-user global Python makes the command available in every shell and terminal, without activating anything. This is the tested configuration and the simplest to use.
- **venv install = isolated copy, only when activated.** If you prefer a virtual environment, activate it before every use (or call the script by its full path). The two installs are independent: installing into a venv does not remove or shadow the global one while the venv is inactive. Pick one and be consistent, so you never wonder which copy a shell resolves (`Get-Command workstream-registration` / `which workstream-registration` shows you).

## Verify the install

From anywhere, run:

```text
> workstream-registration --help

workstream-registration - workstream registration (v1)
usage: workstream-registration [--json] <command> [args]
commands:
  register <workspace> --label <label> --record-source <type>=<uri>... [--kind direct|proxy]
  inspect <workspace>
  link <workspace>
  rebuild <workspace>...
  unregister <workspace>
  resolve-invalid <workspace>
  recover-lock <workspace>
```

Exit code 0 means the script is on PATH and importable. If the command is not found, check which Python/pip you used (below) or start a new terminal so PATH picks up the new Scripts directory.

To confirm which install the shell resolves:

```text
> Get-Command workstream-registration    # Windows PowerShell; `which` on POSIX
```

## Reinstall or upgrade

Because the install is editable, pulling the latest code is normally enough:

```text
git pull
```

The script keeps working and reflects the new code immediately. If the dependency pins changed, or the editable metadata is stale, refresh the install:

```text
pip install --force-reinstall -e .[dev]
```

If you changed Python versions or the install location, reinstall under the new interpreter: `py -3.14 -m pip install -e .[dev]` on Windows.

## Uninstall

```text
pip uninstall workstream-registration
```

This removes the console script and the package metadata from the **active** environment (the one whose pip you ran — a venv install must be uninstalled from inside that venv). It does not touch the repository checkout, the markers you registered, or the projection store (per-user application data; see the [reference](reference.md) support profile). After uninstalling, `workstream-registration` is no longer on PATH and the command fails with "not recognized".

## Troubleshooting

- **`workstream-registration` not found after install:** pip installed into a different environment than the one you are using, or PATH has not refreshed. Run `pip install -e .[dev]` with the same `python` whose `-m pip` you trust, or start a new terminal. `pip show workstream-registration` shows the install location.
- **`sqlite3` missing / conformance runner exits 2:** your CPython build lacks the stdlib `sqlite3` module; use a standard CPython 3.14.x build.
- **Commands exist but the package complains about contracts:** the editable install finds the contracts directory by walking up from the package (`src/`). Keep the checkout intact at its original location; moving it means reinstalling from the new root.
- **Which environment did I install into?** `pip show workstream-registration` reports `Location` (the `site-packages`) and `Editable project location` (the checkout) for the active environment.
