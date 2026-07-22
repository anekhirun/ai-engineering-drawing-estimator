# Developing TakeoffLens

This guide covers the local Windows development and release workflow.

## Environment

- Windows
- PowerShell
- Python 3.12-3.14
- Git

Create the environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use `requirements-mcp.txt` when validating only the headless Plugin runtime.

## Repository layout

```text
.codex-plugin/   Plugin manifest
benchmarks/      Public benchmark schema and examples
desktop/         Experimental PySide6 desktop client
docs/            Product, installation, and developer documentation
mcp/             MCP server, engine, and bundled starter templates
scripts/         Packaging and private benchmark runners
skills/          Agent review workflow and rules
tests/           Unit and contract tests
```

Private drawings and generated artifacts belong in ignored directories such as
`test-runs/`, `output/`, `tmp/`, or `work/`.

## Run validation

```powershell
.\.venv\Scripts\python.exe -m compileall -q mcp desktop scripts tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe mcp\doctor.py
```

Validate the Skill and Plugin:

```powershell
.\.venv\Scripts\python.exe `
  "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" `
  "skills\count-engineering-drawing-symbols"

.\.venv\Scripts\python.exe `
  "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" `
  .
```

## Build the Plugin package

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\build-plugin-package.ps1
```

The packager uses an explicit allowlist and writes:

```text
release/takeoff-lens-plugin-v<version>.zip
```

Before publication, inspect the archive and reject any PDF, DWG, DXF, private
ground truth, output, cache, virtual environment, or machine-specific path.

## Accuracy benchmark

Public files under `benchmarks/` define the schema. Keep real project drawings,
templates, and reviewed ground truth under an ignored private directory.

```powershell
.\.venv\Scripts\python.exe scripts\run-accuracy-benchmark.py `
  test-runs\benchmark-data\manifest.json `
  --output-dir test-runs\accuracy-v0.2.0 `
  --fail-on-threshold
```

Ground truth is accepted only when review is complete, clarification is not
required, and the PDF hash matches. Quality thresholds should be raised from
reviewed evidence, not intuition.

## Adding a symbol

1. Assign a stable uppercase `symbol_id`.
2. Add it to exactly one active system and discipline.
3. Define the legend and visual review rule.
4. Add preferred layer tokens only when supported by drawing evidence.
5. Declare whether a starter or project-specific template is required.
6. Add unit tests for rule exposure and template identity.
7. Add reviewed private ground truth before claiming detector accuracy.

Never merge visually different variants into one class merely to increase an
aggregate count. Indoor and weatherproof equipment, temperature variants, pole
configurations, and other quantity-significant properties should remain
separate when the project legend distinguishes them.

## Adding a Discipline Pack

1. Add the discipline as `planned` in the catalog.
2. Define system IDs, symbol taxonomy, and output semantics.
3. Implement templates, context rules, and review guidance.
4. Add unit and contract tests.
5. Build a multi-project reviewed benchmark.
6. Change the discipline to `active` only when the tool schema and quality gate
   are ready for users.

## Release checklist

- version markers agree across `VERSION`, Plugin manifest, and MCP server;
- unit tests, doctor, Skill validation, and Plugin validation pass;
- README, changelog, installation guide, and migration notes are current;
- the release ZIP is rebuilt and scanned;
- SHA-256 is published beside the ZIP;
- no customer drawing or local artifact is tracked;
- the release notes state supported scope and limitations accurately.
