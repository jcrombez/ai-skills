# Pitfalls met and their fixes

Real cases found while building a manor kit (walls, towers, 45° roofs, U-shaped
courtyard), grouped by symptom. Each line: cause → fix.

## Z-fighting inside a piece

| Symptom | Cause | Fix |
|---|---|---|
| Medallion (oculus) flickering with the wall | `Rotation(+90°, X)` sends local Z to -Y: the disc built in Z ∈ [-0.06, 0] was sunk into the wall, its front face in the wall plane | Build along positive Z (Z ∈ [0, 0.06] → protrudes); pane from Z 0.05 to 0.075 so it overlaps the ring without sharing a plane |
| Bottom of the window reveal flickering | Top of the sill at the same Z as the bottom of the opening | Sill 1 cm above the bottom of the opening |
| Window / gate / balcony frame flickering at the corners | Stiles and rails of the same thickness, coplanar front faces | Stiles ± 5 mm thicker; mullion/transom ± 5–8 mm thinner; stiles starting 5 mm below or above the bottom rail |
| Transom pane | Pane starting at the Z of the rail | Pane offset by 1 cm |
| Threshold, plinth | Back face at Y = wall thickness, like the inner face of the wall | Stop at thickness - 5 mm |
| Cornice corner | Filler box added on top of the prism with the same profile (coplanar tops) | A single shape: the profile limited to the outer square of the corner |
| Balustrade | Pedestal (post) and coping of the same width | Pedestal 1 cm wider, overhanging by 5 mm in X |
| Gutter | Cylinder cutting through the end of the slope (coplanar end faces) | Move the gutter 1 cm away from the slope edge |
| Small roof ridge | Ridge and slopes ending at the same plane | Ridge 1 cm longer on each side |

## Z-fighting between pieces

| Symptom | Cause | Fix |
|---|---|---|
| Brick flickering between corner quoins | End of wall A in the plane of the outer face of wall B (outside corner) | Core in the corner piece, ± 6 mm wider than the wall thickness, over the full height |
| Top of plinth / underside of cornice / string course at inside corners | Two perpendicular bands at the same Z overlap | Bands on ±90° facades raised by 3 mm (placement rule) |
| Plinth corner | Same planes as the straight plinths | Plinth corner 5 mm wider and taller, with an offset middle joint |
| Tower plinth, landing of the steps | Top at the same Z as the wall plinth | Sitting piece 5–10 mm higher than the plinth |
| Tower stone band / string course | Same band height | Tower band 5 mm taller on each side |
| Foot of a dormer flickering | Dormer placed exactly on a slate row (0.4 m pitch) | Offset of 0.85 m instead of 0.80 m |
| Chimney against the ridge | Chimney face on a ridge joint (every 2 m) | Chimney off the grid (X = 9.6 instead of 10) |
| T / L / U roofs | Ends of the wing slopes in the plane of the bottom of the main slope | Wing slopes shifted outwards by 3 mm; valley piece along the meeting line |
| Gable | Inner face of the gable coplanar with the back of the cornice | Gable protruding by 1 cm and 2 cm thinner |
| Garden wall against a pillar | Coping as wide as the pillar | Coping 1 cm narrower; pillar bands offset in Z from the coping |
| Portico entablature against the wall | Back face in the facade plane (and in the door transom plane) | Entablature sunk 5 cm into the wall |

## Other pitfalls

- **`.001` duplicates on every re-run**: the cleanup only walked `coll.objects` (direct
  children); sub-collections survived, and so did objects marked as assets (fake user).
  Walk `all_objects` + `children_recursive`, delete the data of the deleted objects.
- **Piece renamed `Plinth.001`**: another kit in the same file already has an object called
  `Plinth`. The dictionary returned by `Kit.build` stays correct, but the displayed names
  are misleading: prefix the pieces when several kits share a file (e.g. `MAN_Plinth`).
- **Absurd measurements right after generation**: `matrix_world` not recomputed yet.
  Call `bpy.context.view_layer.update()` before reading any matrix.
- **Detector false negatives**: 2D area with the wrong sign = every triangle "clockwise" →
  no overlap detected. Test the area of a known triangle.
- **Detector false positives**: a single ray (`scene.ray_cast`) gets it wrong when volumes
  are nested (a quoin inside a wall); test "point inside" object by object, in 6 directions.
- **Undetected interpenetration** (medallion going through a quoin): this is not
  z-fighting, only a visual close-up check reveals it. Size decorations to stay out of the
  corner areas (0.6 m from each end of a module).
- **45° roof and variable depth**: a run that is a multiple of 2 m forces a wing depth
  that is a multiple of 4 m; plan gable/valley variants per depth.
