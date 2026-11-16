"""Refine the saved Iuno V3 scene in Blender without rebuilding its rig or studio."""

import json
import sys
from collections.abc import Callable
from math import exp
from pathlib import Path
from typing import Any

import bpy  # type: ignore[import-not-found]
from mathutils import Vector  # type: ignore[import-not-found]
from mathutils.bvhtree import BVHTree  # type: ignore[import-not-found]

VIEWS = (
    ("Front orthographic", "preview.png"),
    ("Left 45 orthographic", "left-preview.png"),
    ("Right 45 orthographic", "grid-preview.png"),
    ("Right 90 orthographic", "side-preview.png"),
)


def record_settings(output: Path) -> None:
    scene = bpy.context.scene
    objects = {}
    for obj in scene.objects:
        settings = {
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }
        if obj.type == "MESH":
            settings.update(
                mesh=obj.data.name,
                vertices=len(obj.data.vertices),
                polygons=len(obj.data.polygons),
                materials=[slot.material.name for slot in obj.material_slots if slot.material],
                modifiers=[(modifier.name, modifier.type) for modifier in obj.modifiers],
            )
        if obj.type == "CAMERA":
            settings.update(projection=obj.data.type, orthographic_scale=obj.data.ortho_scale)
        if obj.type == "LIGHT":
            settings.update(energy=obj.data.energy, color=list(obj.data.color), size=obj.data.size)
        objects[obj.name] = settings

    materials = {}
    for paint in bpy.data.materials:
        tree = paint.node_tree
        if not tree:
            continue
        nodes = {}
        for node in tree.nodes:
            sockets: dict[str, Any] = {}
            for socket in node.inputs:
                value = getattr(socket, "default_value", None)
                if isinstance(value, (int, float, bool, str)):
                    sockets[socket.name] = value
                elif value is not None and (
                    hasattr(value, "__iter__") or hasattr(value, "__len__")
                ):
                    sockets[socket.name] = list(value)
            nodes[node.name] = {"type": node.type, "inputs": sockets}
        materials[paint.name] = {
            "nodes": nodes,
            "links": [
                [link.from_node.name, link.from_socket.name, link.to_node.name, link.to_socket.name]
                for link in tree.links
            ],
        }
    report = {
        "source": bpy.data.filepath,
        "objects": objects,
        "materials": materials,
        "render": {
            "engine": scene.render.engine,
            "size": [scene.render.resolution_x, scene.render.resolution_y],
            "scale_percent": scene.render.resolution_percentage,
            "samples": scene.cycles.samples,
            "camera": scene.camera.name,
            "view": scene.view_settings.view_transform,
        },
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def reshape(obj: Any, transform: Callable[[Any], Any]) -> None:
    matrix = obj.matrix_world
    inverse = matrix.inverted()
    for vertex in obj.data.vertices:
        vertex.co = inverse @ Vector(transform(matrix @ vertex.co))
    obj.data.update()


def front_surface(obj: Any, include_modifiers: bool = False) -> Callable[[float, float], float]:
    if include_modifiers:
        bpy.context.view_layer.update()
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
    else:
        evaluated, mesh = None, obj.data
    try:
        points = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
        faces = [tuple(poly.vertices) for poly in mesh.polygons]
        tree = BVHTree.FromPolygons(points, faces)
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()

    def surface(x: float, z: float) -> float:
        point, _, _, _ = tree.ray_cast((x, -2, z), (0, 1, 0), 4)
        if point is None:
            raise ValueError(f"{obj.name} has no surface at ({x:.4f}, {z:.4f})")
        return float(point.y)

    return surface


def replace_skin_patch(
    obj: Any,
    points: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    paints: tuple[Any, ...],
    band: int = 0,
) -> None:
    previous = obj.data
    name = previous.name
    inverse = obj.matrix_world.inverted()
    mesh = bpy.data.meshes.new(name + " polished")
    mesh.from_pydata([inverse @ Vector(point) for point in points], [], faces)
    for paint in paints:
        mesh.materials.append(paint)
    for poly in mesh.polygons:
        poly.use_smooth = True
        poly.material_index = int(band > 0 and poly.index >= band)
    mesh.update()
    obj.data = mesh
    obj.vertex_groups.clear()
    obj.vertex_groups.new(name="Head").add(list(range(len(mesh.vertices))), 1, "REPLACE")
    if previous.users == 0:
        bpy.data.meshes.remove(previous)
        mesh.name = name


def refine_face() -> None:
    face = bpy.data.objects["Face cushion"]

    def cushion(point: Any) -> tuple[float, float, float]:
        x, y, z = point
        chin = max(0, min(1, (1.11 - z) / 0.25)) ** 2
        front = max(0, min(1, (-y - 0.035) / 0.15))
        cheek = exp(-(((abs(x) - 0.35) / 0.16) ** 2) - ((z - 1.045) / 0.11) ** 2)
        return x * (1 + 0.016 * cheek * front), y - 0.008 * front * cheek, z + 0.017 * chin

    reshape(face, cushion)
    face_y = front_surface(face)
    # Each eye is a single thin, weighted mesh. Adjacent color bands share their boundary vertices.
    contour = (
        (1.466, 0.151, 0.182),
        (1.472, 0.138, 0.197),
        (1.486, 0.126, 0.208),
        (1.504, 0.118, 0.219),
        (1.525, 0.113, 0.224),
        (1.547, 0.110, 0.225),
        (1.580, 0.110, 0.224),
        (1.611, 0.115, 0.219),
        (1.637, 0.123, 0.211),
        (1.654, 0.136, 0.204),
        (1.661, 0.151, 0.197),
        (1.664, 0.161, 0.182),
    )
    columns = 11
    for side, sign in (("L", 1), ("R", -1)):
        top = bpy.data.objects[f"Eye {side} embroidered navy"]
        bottom = bpy.data.objects[f"Eye {side} embroidered gold"]
        paints = bottom.data.materials[0], top.data.materials[0]
        points = []
        for height, lo, hi in contour:
            for column in range(columns):
                t = column / (columns - 1)
                x = sign * (0.167 + (lo + (hi - lo) * t - 0.167) * 0.96)
                z = height - 0.305 + 0.003 * (t - 0.5)
                points.append((x, face_y(x, z) - 0.0021, z))
        faces: list[tuple[int, ...]] = []
        for row in range(len(contour) - 1):
            for col in range(columns - 1):
                a = row * columns + col
                face_quad = (a, a + 1, a + 1 + columns, a + columns)
                faces.append(face_quad if sign > 0 else face_quad[::-1])
        replace_skin_patch(top, points, faces, paints, band=4 * (columns - 1))
        bpy.data.objects.remove(bottom, do_unlink=True)

    mouth = bpy.data.objects["Stitched smile"]
    paint = mouth.data.materials[0]
    smile = (
        (-0.053, 1.447),
        (-0.040, 1.440),
        (-0.022, 1.439),
        (-0.008, 1.441),
        (0.005, 1.436),
        (0.025, 1.439),
        (0.041, 1.443),
        (0.050, 1.452),
    )
    points = []
    for index, (base_x, height) in enumerate(smile):
        x = 0.95 * base_x
        half_width = 0.0014 if index in (0, len(smile) - 1) else 0.0032
        for z in (height - 0.305 - half_width, height - 0.305 + half_width):
            points.append((x, face_y(x, z) - 0.0025, z))
    faces = [(i, i + 2, i + 3, i + 1) for i in range(0, len(points) - 2, 2)]
    replace_skin_patch(mouth, points, faces, (paint,))


def shape_sections(
    obj: Any, factors: Callable[[int, int], tuple[float, float, float]], count: int = 16
) -> None:
    vertices = obj.data.vertices
    assert (total := len(vertices) // count) >= 2 and len(vertices) == total * count
    for index in range(total):
        ring = list(vertices[index * count : (index + 1) * count])
        center = sum((vertex.co for vertex in ring), Vector()) / count
        factor = factors(index, total)
        for vertex in ring:
            vertex.co = center + Vector(
                (vertex.co[axis] - center[axis]) * factor[axis] for axis in range(3)
            )
    obj.data.update()


def refine_hair() -> None:
    objects = bpy.data.objects
    fringe = objects["One-piece embroidered felt fringe"]
    rows = 28
    vertices = fringe.data.vertices
    initial = [vertex.co.copy() for vertex in vertices]
    for index, vertex in enumerate(vertices):
        row = index % rows
        if rows <= index < len(vertices) - rows and row < 9:
            blend = 0.23 * (1 - row / 9)
            middle = (initial[index - rows] + initial[index + rows]) * 0.5
            vertex.co = initial[index].lerp(middle, blend)
    fringe.data.update()
    fringe.modifiers["Felt thickness"].thickness = 0.014
    fringe.modifiers["Soft cut felt edge"].width = 0.009
    pile = fringe.modifiers["Short stitched plush fibers"]
    was_visible = pile.show_viewport
    pile.show_viewport = False
    try:
        fringe_y = front_surface(fringe, include_modifiers=True)
    finally:
        pile.show_viewport = was_visible
    reshape(
        objects["Sky blue crescent applique"],
        lambda p: (p.x, min(p.y + 0.004, fringe_y(p.x, p.z) - 0.0036), p.z),
    )
    reshape(
        objects["Folded top hanging tab"], lambda p: (p.x, p.y + 0.003, 1.87 + (p.z - 1.87) * 0.64)
    )
    for side in ("L", "R"):
        for prefix in ("Side felt hair", "Side felt hair tucked layer"):
            reshape(
                objects[f"{prefix} {side}"],
                lambda p: (
                    p.x,
                    p.y + 0.009 * max(0, 1.47 - p.z) / 0.28,
                    p.z + 0.014 * max(0, 1.48 - p.z) / 0.28,
                ),
            )

        def fullness(index: int, total: int, side: str = side) -> tuple[float, float, float]:
            t = index / (total - 1)
            fill = 0.030 * exp(-(((t - 0.57) / 0.24) ** 2))
            pinch = 0.026 * exp(-(((t - 0.15) / 0.12) ** 2))
            tip = max(0.0, (t - 0.83) / 0.17)
            return (
                1 + fill - pinch + tip * (0.026 if side == "R" else 0.015),
                1 + fill - pinch,
                1 - 0.025 * tip,
            )

        shape_sections(objects[f"Long plush ponytail {side}"], fullness)
        band = objects[f"Ivory wraparound hair band {side}"]
        center = sum((vertex.co for vertex in band.data.vertices), Vector()) / len(
            band.data.vertices
        )
        for vertex in band.data.vertices:
            delta = vertex.co - center
            vertex.co = center + Vector((delta.x * 1.015, delta.y * 0.986, delta.z * 0.992))
        band.data.update()


def refine_uniform() -> None:
    objects = bpy.data.objects
    reshape(
        objects["Uniform torso"], lambda p: (p.x, p.y, p.z + 0.017 * max(0, (p.z - 0.77) / 0.12))
    )
    skirt = objects["Pressed ivory pleated skirt"]
    reshape(skirt, lambda p: (p.x, p.y, p.z - 0.007 * max(0, (0.30 - p.z) / 0.10) * (1 - abs(p.x))))
    for side, sign in (("L", 1), ("R", -1)):
        sleeve = objects[f"Continuous sewn sleeve {side}"]
        for vertex in sleeve.data.vertices:
            ring = vertex.index // 16
            if ring <= 1:
                vertex.co.x -= sign * (0.022 if ring == 0 else 0.011)
            if ring == 6:
                vertex.co.y *= 1.033
        sleeve.data.update()
        palm = objects[f"Peach plush mitten {side}"]

        def fit_palm(point: Any, side_sign: int = sign) -> tuple[float, float, float]:
            return point.x - side_sign * 0.006, point.y, point.z + 0.004

        reshape(palm, fit_palm)
        front = objects[f"Blue jacket front {side}"]
        front.modifiers["Jacket fabric thickness"].thickness = 0.005
        reshape(front, lambda p: (p.x, p.y + 0.005, p.z))
        reshape(objects[f"White jacket binding {side}"], lambda p: (p.x, p.y + 0.005, p.z))
        collar = objects[f"White pointed lapel {side}"]
        collar.modifiers["Folded collar thickness"].thickness = 0.009
        bevel = collar.modifiers.new("Soft folded collar edge", "BEVEL")
        bevel.width, bevel.segments = 0.003, 2
        for name in (f"White pointed lapel {side}", f"Collar seam {side}"):
            reshape(objects[name], lambda p: (p.x, p.y + 0.003, p.z + 0.007))
        for index in range(2):
            seam = objects[f"Skirt blue pleat seam {side} {index}"]
            shape_sections(seam, lambda _i, _n: (0.60, 0.49, 0.65))
        for name in (f"Chocolate slipper {side}", f"Caramel slipper front {side}"):
            reshape(objects[name], lambda p: (p.x, p.y, 0.004 + (p.z - 0.004) * 0.94))
        for slope in (-1, 1):
            stitch = objects[f"Slipper diagonal stitch {side} {slope}"]
            shape_sections(stitch, lambda _i, _n: (0.66, 0.62, 0.64))
            reshape(stitch, lambda p: (p.x, p.y, 0.004 + (p.z - 0.004) * 0.94))
    badge = objects["Jacket badge"]
    badge.location.y += 0.005
    for vertex in badge.data.vertices:
        vertex.co.y *= 0.63
    badge.data.update()
    for obj in objects:
        if obj.name == "Blue uniform tie" or obj.name.startswith("Tie pale pinstripe"):
            reshape(obj, lambda p: (p.x, p.y + 0.004, p.z))


def tune_fabrics(rig: Any) -> None:
    settings = {
        # roughness, IOR specular, noise frequency, bump distance
        "Cobalt plush": (0.96, 0.12, 225, 0.008),
        "Navy plush with tint": (0.96, 0.12, 225, 0.008),
        "Warm cream velour": (0.96, 0.11, 238, 0.005),
        "Cream velour with soft blush": (0.96, 0.11, 238, 0.005),
        "Ivory fleece": (0.96, 0.13, 202, 0.008),
        "Ice blue diagonal weave": (0.91, 0.15, 215, 0.006),
        "Warm white diagonal weave": (0.93, 0.13, 208, 0.0055),
        "Deep lake eye thread": (0.88, 0.13, 226, 0.0048),
        "Pale honey eye thread": (0.88, 0.13, 226, 0.0048),
        "Peach pink smile thread": (0.90, 0.12, 226, 0.004),
    }
    for name, (roughness, specular, frequency, distance) in settings.items():
        nodes = bpy.data.materials[name].node_tree.nodes
        shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Specular IOR Level"].default_value = specular
        next(node for node in nodes if node.type == "TEX_NOISE").inputs[
            "Scale"
        ].default_value = frequency
        next(node for node in nodes if node.type == "BUMP").inputs[
            "Distance"
        ].default_value = distance
    for obj in rig.children:
        modifier = obj.modifiers.get("Short stitched plush fibers")
        if modifier is None:
            continue
        sockets = {
            item.name: item.identifier
            for item in modifier.node_group.interface.items_tree
            if item.item_type == "SOCKET"
        }
        density, length = sockets["Density"], sockets["Length"]
        modifier[density] *= 1.10
        if obj.name == "Face cushion":
            modifier[length] = 0.00165
        if obj.name.startswith("Ivory wraparound"):
            modifier[length] = 0.0044


def export_and_render(output: Path, rig: Any) -> None:
    scene = bpy.context.scene
    fibers = []
    for obj in rig.children:
        modifier = obj.modifiers.get("Short stitched plush fibers")
        if modifier is not None:
            fibers.append((modifier, modifier.show_viewport, modifier.show_render))
            modifier.show_viewport = modifier.show_render = False
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (rig, *rig.children):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(output / "iuno-chibi.glb"),
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_animation_mode="ACTIONS",
            export_anim_single_armature=True,
        )
    finally:
        for modifier, visible, rendered in fibers:
            modifier.show_viewport, modifier.show_render = visible, rendered
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    scene.camera = bpy.data.objects[VIEWS[0][0]]
    scene.render.filepath = "//preview.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "iuno-chibi.blend"))
    for camera, filename in VIEWS:
        scene.camera = bpy.data.objects[camera]
        scene.render.filepath = str(output / filename)
        bpy.ops.render.render(write_still=True)


def main(output: Path) -> None:
    input_path = Path(bpy.data.filepath).resolve()
    if not bpy.data.filepath or input_path.parent == output:
        raise ValueError("Open the saved V3 scene and choose a separate output directory")
    rig = bpy.data.objects["Iuno"]
    if rig.get("iuno_revision") == "V4.0":
        raise ValueError("Use the V3 source when running the V4 refinement again")
    record_settings(output / "v3-before-refinement.json")
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    refine_face()
    refine_hair()
    refine_uniform()
    tune_fabrics(rig)
    rig["iuno_revision"] = "V4.0"
    export_and_render(output, rig)


if __name__ == "__main__":
    main(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
