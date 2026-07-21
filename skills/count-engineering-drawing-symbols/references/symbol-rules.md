# Symbol and context rules

## Duplex Socket Outlet

- Core shape: circle with two parallel internal bars.
- Accept rotations at 0, 90, 180, and 270 degrees.
- Search wall runs, corners, both faces near doors, and paired Data Outlet locations.
- Ignore conduit lines passing through or extending from the symbol.

## Single Socket Outlet

- Core shape: circle with one internal line.
- Common CCTV context: nearby `C` and mounting height `+2.80`.
- A nearby `4` can be a circuit/circuit-breaker label, not four outlets.
- Do not reclassify rotated Duplex symbols as Single merely because one bar is obscured.

## Fire Alarm

- Use the current project legend as the authoritative mapping for control panels,
  detectors, bells, manual stations, strobes, and end-of-line accessories.
- Build a project-specific vector template for each Fire Alarm class. v0.1.3 does
  not provide universal Fire Alarm starter geometry.
- Letters such as `S`, `F`, `B`, and `WP` may appear in notes or in compound
  device groups. Treat every match as a review candidate and confirm its context.
- Keep detector temperature ratings separate. Do not infer a 135 F device when
  only a 200 F symbol is visible, or vice versa.
- Count end-of-line as an accessory subtotal unless the requested BOQ explicitly
  includes it in the primary equipment total.

## Deferred systems

Data/Communication and all systems other than Power and Fire Alarm are outside
the v0.1.3 release scope and are planned for v0.2.0.

## Context priority

1. Project legend and clean project-specific vector template.
2. Confirmed company/project mapping.
3. Core geometry and rotation.
4. Wall, corner, door, conduit, height, and nearby tag context.
5. General standard or vision guess.

Wall proximity improves ranking but must never be the sole rejection rule.
