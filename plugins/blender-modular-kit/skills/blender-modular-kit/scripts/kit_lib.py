"""Generic library to generate a modular low/mid poly kit in Blender.

Typical use, in the project's generator script:

    import sys, importlib
    sys.path.insert(0, "<folder containing kit_lib.py>")
    import kit_lib as K
    importlib.reload(K)

    K.define_materials({
        "Brick": ("#8E4A35", 0.9, 0.0),
        "Stone": ("#CFC2A3", 0.85, 0.0),
        "Glass": ("#22303B", 0.08, 0.3),
    })
    kit = K.Kit()
    T, H = 0.3, 3.0

    @kit.piece("Walls")
    def Wall_Window():
        mb = K.MB()
        hole = (0.5, 1.5, 0.8, 2.55)
        mb.wall_hole(2, H, T, hole, "Brick")         # wall with an opening, no boolean
        mb.box(0.5, 0.095, 0.8, 1.5, 0.105, 2.55, "Glass")
        mb.box(0.4, -0.1, 0.72, 1.6, 0.15, 0.81, "Stone")  # sill: 1 cm above the reveal
        return mb

    K.reset("KIT", "KIT_Labels", "EXAMPLE")
    objs = kit.build("KIT", "KIT_Labels")
    P = K.Placer(objs, K.new_coll("EXAMPLE"), bands={"Plinth", "Cornice"})
    for i in range(4):                               # front facade, 4 modules
        P.put("Wall_Window", (*P.along((0, 0), 0, i), 0.6), 0)
    K.tri_report(objs)

Assumed conventions (see SKILL.md): walls on X [0, w], outer face at Y = 0 facing -Y,
inside towards +Y; rotation 0/180/-90/90 = front/back/left/right.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

MAT_DEFS = {}
MAT_PREFIX = "M_"


def srgb(hexstr):
    """'#RRGGBB' -> linear RGBA colour (what the nodes expect)."""
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


def define_materials(defs, prefix="M_"):
    """defs: {name: (hex, roughness, metallic[, emission strength])}."""
    global MAT_PREFIX
    MAT_DEFS.update(defs)
    MAT_PREFIX = prefix


def get_mat(name):
    """Shared material, created on demand from MAT_DEFS."""
    full = MAT_PREFIX + name
    mat = bpy.data.materials.get(full)
    if mat:
        return mat
    col, rough, metal, *rest = MAT_DEFS[name]
    mat = bpy.data.materials.new(full)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = srgb(col)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if rest and rest[0] > 0:
        bsdf.inputs["Emission Color"].default_value = srgb(col)
        bsdf.inputs["Emission Strength"].default_value = rest[0]
    mat.diffuse_color = srgb(col)
    return mat


# ---------------------------------------------------------------------------
# Mesh builder
# ---------------------------------------------------------------------------

class MB:
    """Accumulates closed volumes into a bmesh, with one material per primitive.

    Every primitive accepts an optional matrix M applied to its vertices.
    Reminder: Matrix.Rotation(+pi/2, 4, 'X') sends local Z to world -Y.
    """

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _faces(self, faces, mat):
        m = self._mi(mat)
        for f in faces:
            f.material_index = m

    def _xf(self, verts, M):
        if M is not None:
            bmesh.ops.transform(self.bm, matrix=M, verts=verts)

    def box(self, x0, y0, z0, x1, y1, z1, mat, M=None):
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        za, zb = sorted((z0, z1))
        bm = self.bm
        v = [bm.verts.new(p) for p in (
            (xa, ya, za), (xb, ya, za), (xb, yb, za), (xa, yb, za),
            (xa, ya, zb), (xb, ya, zb), (xb, yb, zb), (xa, yb, zb))]
        idx = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
        self._faces([bm.faces.new([v[i] for i in f]) for f in idx], mat)
        self._xf(v, M)

    def prism(self, prof, a0, a1, axis, mat, M=None):
        """Extrudes a closed 2D profile along an axis.
        axis 'x': profile in (y, z); axis 'y': profile in (x, z)."""
        bm = self.bm

        def p3(u, w, a):
            return (a, u, w) if axis == "x" else (u, a, w)

        A = [bm.verts.new(p3(u, w, a0)) for u, w in prof]
        B = [bm.verts.new(p3(u, w, a1)) for u, w in prof]
        n = len(prof)
        faces = [bm.faces.new(A), bm.faces.new(B[::-1])]
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
        self._faces(faces, mat)
        self._xf(A + B, M)

    def cyl(self, cx, cy, z0, z1, r0, mat, seg=12, r1=None, rot=0.0, M=None):
        """Vertical cylinder, truncated cone, or cone if r1 == 0.
        rot turns the vertices: with rot = pi/seg (e.g. seg=12, rot=15°), a flat face
        looks towards -Y, so windows and details can be placed on it."""
        r1 = r0 if r1 is None else r1
        bm = self.bm

        def ring(z, r):
            return [bm.verts.new((cx + r * math.cos(rot + 2 * math.pi * i / seg),
                                  cy + r * math.sin(rot + 2 * math.pi * i / seg), z))
                    for i in range(seg)]

        bot = ring(z0, r0)
        faces = [bm.faces.new(bot[::-1])]
        if r1 <= 0:
            apex = bm.verts.new((cx, cy, z1))
            faces += [bm.faces.new((bot[i], bot[(i + 1) % seg], apex)) for i in range(seg)]
            verts = bot + [apex]
        else:
            top = ring(z1, r1)
            faces.append(bm.faces.new(top))
            for i in range(seg):
                j = (i + 1) % seg
                faces.append(bm.faces.new((bot[i], bot[j], top[j], top[i])))
            verts = bot + top
        self._faces(faces, mat)
        self._xf(verts, M)

    def sphere(self, cx, cy, cz, r, mat, u=8, v=6, sz=1.0):
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=r,
                                        matrix=Matrix.Translation((cx, cy, cz)) @ Matrix.Diagonal((1, 1, sz, 1)))
        self._faces({f for vert in res["verts"] for f in vert.link_faces}, mat)

    def ico(self, cx, cy, cz, r, mat, sub=1, sz=1.0):
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=r,
                                         matrix=Matrix.Translation((cx, cy, cz)) @ Matrix.Diagonal((1, 1, sz, 1)))
        self._faces({f for vert in res["verts"] for f in vert.link_faces}, mat)

    def wall_hole(self, w, h, t, hole, mat, x0=0.0, z0=0.0):
        """Wall X [x0, x0+w] × Y [0, t] × Z [z0, z0+h] with an opening
        hole = (hx0, hx1, hz0, hz1) in wall-local coordinates (hz0 = 0 for a door).
        Closed mesh built on a vertex grid: no boolean, no n-gon."""
        bm = self.bm
        hx0, hx1, hz0, hz1 = hole
        xs = sorted({0.0, hx0, hx1, w})
        zs = sorted({0.0, hz0, hz1, h})

        def solid(i, k):
            if i < 0 or k < 0 or i >= len(xs) - 1 or k >= len(zs) - 1:
                return False
            cx = (xs[i] + xs[i + 1]) / 2
            cz = (zs[k] + zs[k + 1]) / 2
            return not (hx0 < cx < hx1 and hz0 < cz < hz1)

        F, B = {}, {}
        for i, x in enumerate(xs):
            for k, z in enumerate(zs):
                F[i, k] = bm.verts.new((x0 + x, 0, z0 + z))
                B[i, k] = bm.verts.new((x0 + x, t, z0 + z))
        faces = []
        for i in range(len(xs) - 1):
            for k in range(len(zs) - 1):
                if not solid(i, k):
                    continue
                faces.append(bm.faces.new((F[i, k], F[i + 1, k], F[i + 1, k + 1], F[i, k + 1])))
                faces.append(bm.faces.new((B[i, k + 1], B[i + 1, k + 1], B[i + 1, k], B[i, k])))
                for (ni, nk), (a, b) in (((i - 1, k), ((i, k), (i, k + 1))),
                                         ((i + 1, k), ((i + 1, k), (i + 1, k + 1))),
                                         ((i, k - 1), ((i, k), (i + 1, k))),
                                         ((i, k + 1), ((i, k + 1), (i + 1, k + 1)))):
                    if not solid(ni, nk):
                        faces.append(bm.faces.new((F[a], F[b], B[b], B[a])))
        self._faces(faces, mat)

    def to_object(self, name):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(get_mat(m))
        return bpy.data.objects.new(name, me)


# ---------------------------------------------------------------------------
# Collections, idempotent cleanup
# ---------------------------------------------------------------------------

def new_coll(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def reset(*collection_names):
    """Recursively deletes the given collections, their objects and their data.
    Call it at the top of the generator script so it can be re-run without duplicates."""
    datas = set()
    for cname in collection_names:
        coll = bpy.data.collections.get(cname)
        if not coll:
            continue
        for ob in list(coll.all_objects):
            if ob.data:
                datas.add(ob.data)
            ob.use_fake_user = False  # objects marked as assets have a fake user
            bpy.data.objects.remove(ob, do_unlink=True)
        for child in list(coll.children_recursive):
            bpy.data.collections.remove(child)
        bpy.data.collections.remove(coll)
    for data in datas:
        if data.users:
            continue
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


# ---------------------------------------------------------------------------
# Piece registry and showcase
# ---------------------------------------------------------------------------

class Kit:
    """Piece registry. Each piece is a function with no argument returning an MB,
    named like the object to create, declared with @kit.piece("Category")."""

    def __init__(self):
        self.pieces = []

    def piece(self, category):
        def deco(fn):
            self.pieces.append((category, fn))
            return fn
        return deco

    def build(self, kit_coll, labels_coll=None, y0=50.0, gap=2.0, row_gap=5.0,
              label_size=0.35, asset_tag=None):
        """Creates every piece, sorted by category (one sub-collection and one row per
        category), with text labels in a separate collection.
        Returns {name: object}."""
        kit = new_coll(kit_coll)
        labels = new_coll(labels_coll) if labels_coll else None
        cats = {}
        for cat, fn in self.pieces:
            cats.setdefault(cat, []).append(fn)
        objs = {}
        y = y0
        for cat, fns in cats.items():
            sub = new_coll(f"{kit_coll}_{cat}", kit)
            x, depth = 0.0, 0.0
            for fn in fns:
                ob = fn().to_object(fn.__name__)
                sub.objects.link(ob)
                objs[fn.__name__] = ob
                xs = [v[0] for v in ob.bound_box]
                ys = [v[1] for v in ob.bound_box]
                ob.location = (x - min(xs), y - min(ys), 0)
                depth = max(depth, max(ys) - min(ys))
                if labels:
                    _label(labels, ob.name, (x, y - 1.0, 0.01), label_size)
                x += (max(xs) - min(xs)) + gap
            if labels:
                _label(labels, cat.upper(), (-8.0, y, 0.01), label_size * 2.3, prefix="cat_")
            y += depth + row_gap
        if asset_tag:
            for ob in objs.values():
                ob.asset_mark()
                ob.asset_data.tags.new(asset_tag)
        return objs


def _label(coll, text, loc, size, prefix="lbl_"):
    cu = bpy.data.curves.new(prefix + text, "FONT")
    cu.body = text
    cu.size = size
    ob = bpy.data.objects.new(prefix + text, cu)
    ob.location = loc
    coll.objects.link(ob)


def tri_report(objs):
    """Prints the triangle count per piece and the total."""
    total = 0
    for name, o in objs.items():
        n = sum(len(p.vertices) - 2 for p in o.data.polygons)
        total += n
        print(f"  {name:24s} {n:6d} tris")
    print(f"Kit: {len(objs)} pieces, {total} triangles")
    return total


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

class Placer:
    """Places linked duplicates of the kit pieces (editing a piece updates the example).

    bands: names of the "horizontal band" pieces (plinth, string course, cornice…). When
    placed on a facade oriented along Y (rotation ±90), they are raised by band_dz so their
    tops/bottoms are not coplanar with those of the perpendicular facade.
    """

    def __init__(self, objs, coll, origin=(0.0, 0.0), bands=(), band_dz=0.003):
        self.objs, self.coll, self.origin = objs, coll, origin
        self.bands, self.band_dz = set(bands), band_dz

    def put(self, name, loc, rz=0.0):
        ob = bpy.data.objects.new(name + "_ex", self.objs[name].data)
        dz = self.band_dz if name in self.bands and round(rz) % 180 != 0 else 0.0
        ob.location = (loc[0] + self.origin[0], loc[1] + self.origin[1], loc[2] + dz)
        ob.rotation_euler = (0, 0, math.radians(rz))
        self.coll.objects.link(ob)
        return ob

    @staticmethod
    def along(start, rz, i, inward=0.0, module=2.0):
        """(x, y) of module i of a facade starting at `start` with rotation rz:
        modules advance along local X, `inward` offsets along local Y
        (towards the inside for a wall, up the slope for a roof)."""
        r = math.radians(rz)
        ax, ay = round(math.cos(r), 6), round(math.sin(r), 6)
        return (start[0] + ax * module * i - ay * inward, start[1] + ay * module * i + ax * inward)

    def ground(self, center, size=40.0, mat="Grass"):
        """Ground plane (not part of the kit); mat must exist in MAT_DEFS."""
        me = bpy.data.meshes.new("Ground")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(get_mat(mat))
        ground = bpy.data.objects.new("Ground", me)
        ground.location = (center[0] + self.origin[0], center[1] + self.origin[1], -0.001)
        self.coll.objects.link(ground)
        return ground


def look_at(ob, target):
    """Points a camera/light at a location."""
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
