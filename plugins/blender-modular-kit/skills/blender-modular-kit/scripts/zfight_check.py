"""Z-fighting detector for Blender modular kits.

Looks for coplanar faces, facing the same way, that overlap:
  - within a single piece (kit collection);
  - between different pieces placed side by side (example collections).
Invisible faces are skipped: faces lying on the ground facing down, and faces buried in
a volume (a point just in front of the face is inside a closed object).

Does NOT detect interpenetrations (a decoration going through another piece): check
those by eye.

From Blender:
    import sys; sys.path.insert(0, "<folder of this file>")
    import zfight_check
    zfight_check.run(kit="KIT", examples=["EXAMPLE"], detail=2)
or open this file in the text editor, set KIT / EXAMPLES below and Run Script.

Reading the report: one line per pair of pieces with the overlapping area;
with detail > 0, the normal and position of the overlap in the frame of the first
piece named ("local(...)"), which points to the face to fix.
"""

from collections import defaultdict

import bpy
from mathutils import Vector

# Defaults (used by Run Script; run() accepts the same as parameters)
KIT = "KIT"              # kit pieces collection ("within a piece" check)
EXAMPLES = ["EXAMPLE"]   # assembly collections ("between pieces" check)
PLANE_TOL = 0.002        # max distance between two planes considered identical (m)
MIN_AREA = 1e-4          # overlaps below this are ignored (m²)
GROUND_Z = 0.0           # ground level: undersides of pieces resting on it are ignored
DUP_SUFFIX = "_ex"       # suffix of example duplicates, stripped in the report


def base_name(name):
    """Name of the source piece: without .001 suffix or duplicate suffix."""
    return name.split(".")[0].removesuffix(DUP_SUFFIX)


def clip(poly, a, b):
    """Sutherland-Hodgman: keeps the part of poly on the left of edge a->b."""
    out = []
    def side(p):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        sp, sq = side(p), side(q)
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def area(poly):
    return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))


def ccw(tri):
    return tri if area(tri) > 0 else tri[::-1]


def overlap(t1, t2):
    """Intersection polygon of two 2D triangles (empty list if none)."""
    poly = t1
    for i in range(3):
        poly = clip(poly, t2[i], t2[(i + 1) % 3])
        if len(poly) < 3:
            return []
    return poly


BOXES = []  # (object, min, max) in world coordinates, filled by check()
DIRS = [Vector(d) for d in ((0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))]


def world_boxes(objs):
    out = []
    for ob in objs:
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        out.append((ob, lo, hi))
    return out


def inside(ob, q):
    """True if q is inside a closed volume of the object: in at least one direction,
    the first face hit is an exit face (normal along the ray)."""
    inv = ob.matrix_world.inverted()
    ql = inv @ q
    rot = inv.to_3x3()
    for d in DIRS:
        dl = (rot @ d).normalized()
        hit, _loc, hn, _i = ob.ray_cast(ql, dl, distance=50.0)
        if hit and hn.dot(dl) > 0:
            return True
    return False


def visible(p, n):
    """False if the face rests on the ground facing down, or is buried in a volume."""
    if n.z < -0.99 and p.z < GROUND_Z + 0.05:
        return False
    q = p + n * 0.004
    for ob, lo, hi in BOXES:
        if lo.x <= q.x <= hi.x and lo.y <= q.y <= hi.y and lo.z <= q.z <= hi.z and inside(ob, q):
            return False
    return True


def collect(objs):
    """World triangles grouped by plane: key -> [(object, 3D points)]."""
    buckets = defaultdict(list)
    for ob in objs:
        me = ob.data
        me.calc_loop_triangles()
        mw = ob.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        verts = [mw @ v.co for v in me.vertices]
        for tri in me.loop_triangles:
            n = (nmat @ tri.normal).normalized()
            p = [verts[i] for i in tri.vertices]
            d = n.dot(p[0])
            key = (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(d / PLANE_TOL))
            buckets[key].append((ob, p))
    return buckets


def basis(key):
    n = Vector(key[:3]).normalized()
    u = n.orthogonal().normalized()
    return n, u, n.cross(u)


def to_2d(key, items):
    """Projects the triangles of one plane into a shared 2D basis."""
    n, u, v = basis(key)
    out = []
    for ob, p in items:
        t2 = ccw([(q.dot(u), q.dot(v)) for q in p])
        xs, ys = [q[0] for q in t2], [q[1] for q in t2]
        out.append((ob, t2, (min(xs), min(ys), max(xs), max(ys))))
    return out


def check(objs, intra):
    """intra=True: only within a single object; False: between different objects."""
    results = defaultdict(float)
    where = {}
    BOXES[:] = world_boxes(objs)
    for key, items in collect(objs).items():
        if len(items) < 2:
            continue
        n, u, v = basis(key)
        d = n.dot(items[0][1][0])
        items = sorted(to_2d(key, items), key=lambda it: it[2][0])
        for i, (oa, ta, ba) in enumerate(items):
            for ob, tb, bb in items[i + 1:]:
                if bb[0] >= ba[2] - 1e-6:
                    break
                if (oa is ob) != intra:
                    continue
                if bb[1] >= ba[3] - 1e-6 or ba[1] >= bb[3] - 1e-6:
                    continue
                poly = overlap(ta, tb)
                a = abs(area(poly)) if poly else 0.0
                if a <= MIN_AREA:
                    continue
                cx = sum(q[0] for q in poly) / len(poly)
                cy = sum(q[1] for q in poly) / len(poly)
                p = u * cx + v * cy + n * d
                if visible(p, n):
                    pair = tuple(sorted((base_name(oa.name), base_name(ob.name))))
                    results[pair] += a
                    local = oa.matrix_world.inverted() @ p
                    where.setdefault(pair, []).append((oa.name, ob.name, key, local, a))
    return results, where


def report(title, results, where, detail=0):
    print(f"\n== {title}: {len(results)} cases ==")
    for pair, a in sorted(results.items(), key=lambda kv: -kv[1]):
        oa, ob, key, _, _ = where[pair][0]
        print(f"  {a:8.3f} m²  {pair[0]} / {pair[1]}   e.g.: {oa} / {ob}")
        seen = set()
        for _oa, _ob, k, loc, _ar in where[pair]:
            if len(seen) >= detail:
                break
            sig = (k[:3], round(loc.x, 1), round(loc.y, 1), round(loc.z, 1))
            if sig in seen:
                continue
            seen.add(sig)
            print(f"        n={k[:3]} local({_oa})=({loc.x:.2f}, {loc.y:.2f}, {loc.z:.2f})")


def _meshes(cname):
    coll = bpy.data.collections.get(cname)
    if coll is None:
        print(f"(collection not found: {cname})")
        return []
    return [o for o in coll.all_objects if o.type == "MESH"]


def run(kit=None, examples=None, detail=0, min_area=None):
    """Runs the checks and prints the report. Returns {title: {pair: area}}."""
    global MIN_AREA
    if min_area is not None:
        MIN_AREA = min_area
    kit = KIT if kit is None else kit
    examples = EXAMPLES if examples is None else examples
    bpy.context.view_layer.update()  # up-to-date world matrices if the kit was just generated
    out = {}
    if kit:
        title = "Within a piece"
        res, where = check(_meshes(kit), intra=True)
        report(title, res, where, detail)
        out[title] = dict(res)
    for cname in examples:
        title = f"Between pieces ({cname})"
        res, where = check(_meshes(cname), intra=False)
        report(title, res, where, detail)
        out[title] = dict(res)
    return out


if __name__ == "__main__":
    run()
