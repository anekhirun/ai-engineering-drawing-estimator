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

## Data Outlet

- Common shape: broken/open `C`-like geometry.
- Often paired immediately beside a Duplex Socket Outlet.
- Distinguish from door arcs, revision clouds, and open circles in annotations.

## Context priority

1. Project legend and clean project-specific vector template.
2. Confirmed company/project mapping.
3. Core geometry and rotation.
4. Wall, corner, door, conduit, height, and nearby tag context.
5. General standard or vision guess.

Wall proximity improves ranking but must never be the sole rejection rule.
