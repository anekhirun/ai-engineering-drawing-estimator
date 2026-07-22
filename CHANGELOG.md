# Changelog

All notable public changes to TakeoffLens are documented here.

## [0.2.1] - 2026-07-22

### Changed

- Updated canonical repository links to `anekhirun/Takeoff-Lens-Plugin`.
- Added exact Hermes Desktop Skill and MCP installation instructions.
- Aligned Plugin, MCP server, candidate-review page, and documentation versions.

### Validation

- Full unit-test suite and MCP doctor.
- Plugin and Skill validators.
- Release archive content and SHA-256 verification.

## [0.2.0] - 2026-07-22

### Added

- TakeoffLens product identity and `takeoff-lens` Plugin/MCP namespace.
- Active/planned discipline catalog.
- Detection manifests with PDF, template, and candidate SHA-256 provenance.
- Complete candidate pools with shortlisted, filtered, and ranked-out states.
- Reviewed accuracy evaluation with precision, recall, F1, exact TP/FP/FN IDs,
  and filter/shortlist miss attribution.
- Fire Alarm indoor and weatherproof variants.
- Template schema v2 with declared symbol identity.
- Public benchmark schema, examples, runner, and quality gates.
- Ten-tool MCP surface including `get_discipline_catalog` and
  `evaluate_detection_accuracy`.

### Changed

- Candidate Filtering v3 prioritizes clean overlapping candidates during NMS.
- Fire Alarm detection can use confirmed system-layer evidence.
- A count is final only when review and provenance are both complete.
- The managed Plugin runtime now uses the TakeoffLens data directory and
  `TAKEOFFLENS_PYTHON`, with the legacy variable retained as an alias.

### Validation

- 27 unit tests.
- MCP doctor validates ten tools.
- Plugin and Skill validators pass.
- First reviewed Fire Alarm regression baseline preserves recall at `1.000` on
  one private vector sheet. This is not a general production-accuracy claim.

## [0.1.5] - 2026-07-22

- Added installable Codex Plugin and local marketplace packaging.
- Split headless MCP dependencies from the optional Desktop App.
- Added a first-run managed Python environment.

## [0.1.4] - 2026-07-22

- Added shared native sheet context and Page Profiler v2.
- Added layer-signature analysis and project mapping support.
- Added Candidate Filtering v2 and compact MCP responses.

## [0.1.3] - 2026-07-21

- Expanded Power, Lighting, Fire Alarm, Data/Voice, and CCTV/Security scope.
- Added one-call sheet audit preparation and review artifacts.

[0.2.1]: https://github.com/anekhirun/Takeoff-Lens-Plugin/releases/tag/v0.2.1
[0.2.0]: https://github.com/anekhirun/Takeoff-Lens-Plugin/releases/tag/v0.2.0
[0.1.5]: https://github.com/anekhirun/Takeoff-Lens-Plugin/releases/tag/v0.1.5
[0.1.4]: https://github.com/anekhirun/Takeoff-Lens-Plugin/releases/tag/v0.1.4
[0.1.3]: https://github.com/anekhirun/Takeoff-Lens-Plugin/releases/tag/v0.1.3
