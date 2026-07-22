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

## Other Power devices

- Power Receptacle 3P+N+E uses the filled triangular pole marker from the current legend; keep pole count, ampere rating, and WP context in review notes.
- Non-Fuse Disconnecting Switch is separate from socket outlets and power receptacles even when it shares the same circuit run.

## Fire Alarm

- Use the current project legend as the authoritative mapping for control panels,
  detectors, bells, manual stations, strobes, and end-of-line accessories.
- Build a project-specific vector template for each Fire Alarm class. v0.1.4 does
  not provide universal Fire Alarm starter geometry.
- Letters such as `S`, `F`, `B`, and `WP` may appear in notes or in compound
  device groups. Treat every match as a review candidate and confirm its context.
- Keep detector temperature ratings separate. Do not infer a 135 F device when
  only a 200 F symbol is visible, or vice versa.
- Count end-of-line as an accessory subtotal unless the requested BOQ explicitly
  includes it in the primary equipment total.

## Data and Voice

- Treat the circle containing `C` as Data Outlet (RJ45) only when its complete geometry matches the project legend; do not confuse it with a nearby above-ceiling suffix `C`.
- Keep wall and floor telephone/data outlets separate.
- Panels and cabinets such as PABX, MDF, patch panels, and TC require the current project legend.

## CCTV and Security

- Read camera suffixes from the drawing note: fixed, pan-tilt, and dummy camera are separate classes.
- Keep CCTV cameras separate from PIR detectors, magnetic contacts, access-control readers, locks, release buttons, and security panels.
- Use the current project legend for every class and exclude Fire Alarm symbols even when both systems share one sheet.

## Lighting

- Keep normal luminaires, emergency luminaires, exit signs, switches, control devices, and junction boxes as separate classes.
- Use the current project legend to distinguish line, rectangle, diffuser, industrial, weatherproof, recessed, high/low-bay, floodlight, and street-light symbols.
- Lowercase suffixes such as `a` through `i` are switching references, not fixture quantities. A combined `a-i` switch bank represents nine switch ways at one physical location; report both values.
- Wiring arrows and switch-reference labels are context, not additional devices.
- Keep the fan switch with indicating lamp separate from ordinary one-way lighting switches.
- Count emergency-lighting accessories separately when the BOQ requires a normal/emergency split.
- Keep `LED 2x10W/2x20W recessed diffuser` separate from `LED 10W/20W surface-mounted weatherproof IP65`; their plan geometry must be mapped through the project legend rather than inferred from orientation alone.

## v0.1.4 systems

Power, Lighting, Fire Alarm, Data/Voice, and CCTV/Security are included in v0.1.4.

## Context priority

1. Project legend and clean project-specific vector template.
2. Confirmed company/project mapping.
3. Core geometry and rotation.
4. Wall, corner, door, conduit, height, and nearby tag context.
5. General standard or vision guess.

Wall proximity improves ranking but must never be the sole rejection rule.

## Confirmed vector-layer mappings

- Normalize path width and height into short/long extents so 0- and 90-degree
  instances share one signature.
- A layer name and geometric signature identify a candidate group, not an
  equipment class. Assign `symbol_id` only after checking the current project
  legend or receiving an explicit user confirmation.
- Persist the confirmed mapping per project/sheet and reuse it. If two mappings
  match one signature, mark it ambiguous and request clarification.
- Keep full candidate coordinates in the audit JSON; return only counts and
  artifact paths in routine compact responses.
