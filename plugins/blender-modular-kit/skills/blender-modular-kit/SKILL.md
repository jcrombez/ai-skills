---
name: blender-modular-kit
description: Rules and scripts for designing a modular low/mid poly 3D kit in Blender (buildings, manors, castles, houses, ramparts, fences, game environment pieces, anything assembled on a grid) with Python/bpy or the Blender MCP, then assembling an example and hunting down z-fighting. Use it whenever the user asks to create, extend or fix a kit of modular pieces, an "asset kit", walls/roofs/corners to snap together, a building made of pieces, or reports z-fighting / flickering / shimmering faces on an assembly, even if they never say the word "kit".
---

# Blender modular kit (low/mid poly)

A modular kit is a set of pieces that snap together on a grid with no manual fixing.
Its quality depends less on how pretty each piece is than on **strict conventions**
(everyone places pieces the same way) and on **no coplanar faces** between neighbouring
pieces (otherwise z-fighting everywhere). This skill sums up what worked and the
pitfalls already hit.

Bundled resources (in `scripts/` next to this file):

| File | Purpose |
|---|---|
| `scripts/kit_lib.py` | Library: materials, `MB` bmesh builder (boxes, prisms, cylinders, wall with an opening…), piece registry, idempotent cleanup, labelled showcase, `Placer` to assemble facade by facade |
| `scripts/zfight_check.py` | Z-fighting detector: coplanar, same-facing, overlapping faces, hidden faces excluded |
| `references/pitfalls.md` | Detailed list of pitfalls met and how they were fixed (read it when in doubt or debugging) |

## Workflow

1. **Set the conventions before the first piece** (next section) and write them at the
   top of the generator script. If the user specified nothing, use the defaults below and
   say so.
2. **Generate the whole kit from a single, re-runnable Python script** (a file in the
   user's project, one function per piece). Use `kit_lib.py` rather than rewriting the
   primitives. Running the script N times must not create duplicates.
3. **Assemble at least one example** with linked duplicates (`Placer`). It is the only real
   test of the kit: fitting problems only show up once pieces are assembled.
4. **Check**: run `zfight_check.py`, fix until only a few cm² of residual contacts remain,
   then **look** (the MCP `look` tool or screenshots) at corners, roof junctions and
   details in close-up.
5. Save the `.blend` and deliver the script.

### Using the scripts from Blender

```python
import sys, importlib
sys.path.insert(0, "<skill path>/scripts")
import kit_lib, zfight_check
importlib.reload(kit_lib); importlib.reload(zfight_check)   # after editing them
```

In the project's generator script, copy `kit_lib.py` next to the script (the project
should stay self-contained) or import it from the skill if the user prefers.
See the `kit_lib.py` docstring for a minimal piece-and-placement example.

To test without damaging the user's scene: use dedicated collection names (`TST_*`),
then `kit_lib.reset(...)` at the end of the test.

## Conventions (proven defaults)

- **Grid**: 2 m module, 3 m storey, 0.6 m plinth, 0.3 m wall thickness.
  Units in metres, Z up.
- **Walls**: origin at the bottom left of the **outer face**; the wall spans X [0, 2],
  the inside towards +Y, the outer face looks towards -Y.
- **Facade Z rotations**: 0 front, 180 back, -90 left side, 90 right side.
  With these conventions the same piece (wall, plinth, cornice, roof slope) goes on any
  facade with just (start point, rotation): that is what
  `Placer.along(start, rz, i, inward)` does.
- **Corner pieces**: origin on the outer corner, building towards +X / +Y.
- **45° roof**: slope pieces with a 2 m run, stacked every (+2 Y, +2 Z) from the foot of
  the slope; an eave piece (overhang + gutter) placed at the same point as the first
  slope. One fixed building depth (e.g. 8 m) per set of gables and valleys.
- **Round pieces** (towers): pick the segment count and rotation so that a flat face looks
  towards -Y, to place windows and details on it.
- **Budget**: 10–300 tris for a wall piece, < 700 for the busiest ones (gate, portico).
  Measure and print the tris per piece at the end of generation.

## Building the pieces

- Build in **bmesh** from closed volumes (boxes, extruded prisms, cylinders), then
  `remove_doubles` + `recalc_face_normals`. Closed volumes give reliable normals and let
  the detector tell visible faces from hidden ones.
- **Wall with an opening**: vertex grid around the opening (`MB.wall_hole`), no boolean.
  Clean topology, no degenerate n-gons, no evaluation cost.
- Details **clearly protruding** (surrounds, sills, quoins, string courses: 3 to 8 cm),
  joinery **recessed** into the reveal. Relief makes the low poly style; coplanarity makes
  z-fighting.
- **Materials**: one material per colour, shared by all pieces (`get_mat`), colours set on
  the Principled node (find it by `type`, never by its localised name). Also set
  `diffuse_color` for the viewport.
- Think of **decoration next to a neighbouring piece**: a medallion centred on a 2 m module
  must not bite into a corner quoin (0.6 m on each side) → stay in the usable area.

## Anti z-fighting rules (the core of it)

Principle: **two visible faces must never lie in the same plane, face the same way and
overlap**, neither inside a piece nor between two pieces placed by the kit rules. A gap of
**3 to 5 mm** is enough and stays invisible; prefer moving the "secondary" piece (detail,
corner piece, piece sitting on another).

Inside a piece:
- Frames: stiles stick out a few mm in front of/behind the rails; mullions and
  intermediate transoms are recessed. Same for posts/handrails (balustrades, railings,
  gates): the post is slightly wider and slightly taller.
- A window sill sticks out 1 cm **above** the bottom of the reveal (otherwise it is
  coplanar with the bottom face of the opening).
- A pane does not start at the same Z as the rail holding it.
- Parts touching the inner face of a wall (thresholds, plinths) stop 5 mm short of it.
- Check the **direction of sub-element rotations**: `Matrix.Rotation(+90°, 'X')` sends
  local Z to world **-Y**. A "protruding" medallion built along negative Z ends up sunk
  into the wall, its front face exactly in the wall plane (real case).

Between pieces:
- **Outside corners**: the end of wall A lies in the plane of the face of the
  perpendicular wall B. The corner piece must contain a **core** slightly wider
  (± 6 mm) that encloses those wall ends.
- **Crossing horizontal bands** (plinth, string course, cornice): on facades oriented
  along Y (rotation ±90), raise them by 3 mm (`Placer` does it for the names listed in
  `bands`). The corner pieces of these bands are slightly wider / taller than the straight
  pieces, or limited to the outer square.
- **Pieces sitting on others** (steps on a plinth, tower on a plinth, balustrade on an
  entablature): the sitting piece sticks out by 5 mm or sinks into its support.
- **Placement off the grid joints**: anything placed on a surface with a periodic pattern
  (slate rows, ridge joints every 2 m) must avoid landing exactly on a joint (e.g. dormer
  at 0.85 m rather than 0.80 m on a 0.4 m pitch; chimney at X = 9.6 rather than 10).
- **Crossing roofs**: shift a wing's slopes by 3 mm so their ends do not lie in the plane
  of the bottom of the main slope; finish valleys with a dedicated piece (zinc strip laid
  along the valley line).

## Corners and junctions

- **Outside corner**: corner piece (quoins) + plinth and cornice corners.
- **Inside corner**: with walls "outer face at the origin, inside towards +Y", two
  perpendicular walls leave an empty space inside and no visible hole; two cornices with
  the same profile crossing at 90° form a mitre on their own. Only the 3 mm band offset
  is needed.
- **L / U / T plans**: all wings as deep as the main body, ridges at the same height; the
  slopes meet in valleys (concave) with no special piece other than the valley strip.
  Only truly outer facades get an eave.

## Generator script hygiene

- **Idempotent**: before regenerating, delete the kit collections **recursively**
  (`coll.all_objects` and `children_recursive`, not just `coll.objects`), then the
  meshes/curves of those objects. Otherwise `.001` copies pile up on every run (objects
  marked as assets have a fake user and survive).
- Call `bpy.context.view_layer.update()` before reading `matrix_world` of objects created
  in the same script (otherwise identity matrices → wrong measurements and detections).
- **Showcase**: one sub-collection per category, pieces in rows with text labels in a
  separate collection (to exclude from export), far from the example.
- **Assets**: `asset_mark()` + a tag to find the pieces in the Asset Browser.
- **Examples**: linked duplicates (`bpy.data.objects.new(name, piece.data)`), so editing a
  piece updates every assembly. Keep older examples, offset to the side.

## Checking

```python
zfight_check.run(kit="KIT", examples=["EXAMPLE"], detail=2)
```

- "Within a piece" section: construction defects of the piece → fix the piece.
- "Between pieces" section: fitting defects → fix the corner piece / the placement / the
  offset rule, never by patching a single example if the defect will come back with every
  assembly.
- `local(...)` positions are in the frame of the first piece named: they point to the
  exact face to fix.
- Goal: 0 cases, or only contacts < 0.01 m² in barely visible areas (say so).
- The detector does not see **interpenetrations** (a medallion going through a quoin):
  those are spotted by eye, in close-up, at the corners.

For details on the cases already met and their fix, read `references/pitfalls.md`.
