"""Build the GridWorld archive props with their one-cell and hinge anchors."""

import sys
from math import cos, pi, sin
from pathlib import Path
from typing import Any

import bmesh  # type: ignore[import-not-found]
import bpy  # type: ignore[import-not-found]

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.blender_key_door_scene import box, finish, material, sphere  # noqa: E402

Point = tuple[float, float, float]


def paint(name: str, color: str, metallic: float = 0, roughness: float = 0.65) -> Any:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    rgb = tuple(linear(int(color[i : i + 2], 16)) for i in (0, 2, 4))
    surface = material(name, (rgb[0], rgb[1], rgb[2]), metallic)
    surface.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value = roughness
    return surface


def root(name: str, origin: Point = (0, 0, 0)) -> Any:
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = origin
    obj.empty_display_size = 0.12
    return obj


def block(
    parent: Any, name: str, at: Point, size: Point, surface: Any, bevel: float = 0.016
) -> None:
    box(name, at, size, surface, bevel)
    bpy.context.object.parent = parent


def outline(
    parent: Any,
    name: str,
    profile: list[tuple[float, float]],
    thickness: float,
    surface: Any,
    bevel: float,
) -> None:
    count = len(profile)
    vertices = [(x, y, z) for x in (-thickness / 2, thickness / 2) for y, z in profile]
    faces = [tuple(range(count)), tuple(reversed(range(count, 2 * count)))]
    for i in range(count):
        j = (i + 1) % count
        faces.append((i, j, j + count, i + count))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    topology = bmesh.new()
    try:
        topology.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(topology, faces=list(topology.faces))
        topology.to_mesh(mesh)
    finally:
        topology.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    mesh.materials.append(surface)
    rounded = obj.modifiers.new("Soft carved edges", "BEVEL")
    rounded.width = bevel
    rounded.segments = 2
    obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")


def arc(radius: float, spring: float) -> list[tuple[float, float]]:
    return [(radius * cos(i * pi / 16), spring + radius * sin(i * pi / 16)) for i in range(17)]


def ring(parent: Any, name: str, at: Point, radius: float, width: float, surface: Any) -> None:
    bpy.ops.mesh.primitive_torus_add(
        major_segments=32, minor_segments=8, location=at, major_radius=radius, minor_radius=width
    )
    finish(name, surface).parent = parent
    bpy.ops.object.shade_smooth()


def build(output: Path) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    plinth = paint("Terracotta plinth", "655149")
    stone = [paint("Sandstone", "AD9577"), paint("Ivory stone", "CEB899")]
    ink = paint("Blue slate", "34485C")
    edge = paint("Slate cornice", "5D7583")
    brass = paint("Antique brass", "D5A452", metallic=0.24, roughness=0.38)
    door_face = paint("Petrol enamel", "336B69")
    door_inset = paint("Pale enamel", "578B81")
    jade = paint("Exit enamel", "4BBDAB")

    for index in range(2):
        floor = root(f"Floor {index} 0", (index, 0, 0))
        block(floor, "Terracotta edge", (0, 0, -0.095), (0.98, 0.98, 0.15), plinth)
        block(floor, "Carved limestone tile", (0, 0, -0.029), (0.956, 0.956, 0.058), stone[index])

    wall = root("Wall 0", (0, 1, 0))
    block(wall, "Wall foot", (0, 0, 0.043), (0.92, 0.81, 0.086), ink)
    block(wall, "Cutaway wall", (0, 0, 0.205), (0.88, 0.78, 0.31), ink)
    block(wall, "Stone cornice", (0, 0, 0.36), (0.92, 0.82, 0.065), edge)
    block(wall, "Brass trim", (0, 0, 0.32), (0.903, 0.797, 0.018), brass, 0.005)

    for name, side in (("Door jamb", -1), ("Door jamb.001", 1)):
        jamb = root(name)
        block(jamb, "Arch base", (0, side * 0.43, 0.066), (0.22, 0.13, 0.132), ink)
        block(jamb, "Arch upright", (0, side * 0.43, 0.43), (0.19, 0.12, 0.72), stone[1])
    lintel = root("Door lintel")
    outline(
        lintel, "Stone arch", [*arc(0.49, 0.77), *reversed(arc(0.37, 0.77))], 0.19, stone[1], 0.009
    )
    outline(
        lintel,
        "Bronze arch band",
        [*arc(0.405, 0.77), *reversed(arc(0.372, 0.77))],
        0.21,
        brass,
        0.005,
    )

    panel = root("Door panel")
    outline(
        panel,
        "Rounded enamel door",
        [(0.35, 0.055), *arc(0.35, 0.76), (-0.35, 0.055)],
        0.10,
        door_face,
        0.014,
    )
    outline(
        panel,
        "Raised inner panel",
        [(0.26, 0.17), *arc(0.26, 0.72), (-0.26, 0.17)],
        0.108,
        door_inset,
        0.009,
    )
    block(panel, "Brass push plate", (0.058, 0, 0.36), (0.024, 0.5, 0.042), brass, 0.008)
    handle = root("Door handle")
    sphere("Door knob", (0.089, -0.21, 0.52), 0.055, brass)
    bpy.context.object.parent = handle

    bow = root("Key bow", (-1.29, 0, 0))
    ring(bow, "Key bow ring", (-0.16, 0, 0.155), 0.115, 0.034, brass)
    shaft = root("Key shaft", (-1.29, 0, 0))
    block(shaft, "Key shank", (0.11, 0, 0.155), (0.35, 0.065, 0.065), brass)
    tooth = root("Key tooth", (-1.29, 0, 0))
    block(tooth, "Key bit", (0.243, -0.053, 0.155), (0.076, 0.157, 0.067), brass)

    goal = root("Goal tile", (2, 0, 0))
    block(goal, "Exit plinth", (0, 0, 0.029), (0.82, 0.82, 0.058), ink, 0.048)
    block(goal, "Exit tile", (0, 0, 0.076), (0.73, 0.73, 0.048), jade, 0.044)
    marker = root("Goal marker", (2, 0, 0))
    ring(marker, "Exit brass inlay", (0, 0, -0.022), 0.25, 0.016, brass)

    bpy.ops.wm.save_as_mainfile(filepath=str(output / "gallery-kit.blend"))
    bpy.ops.export_scene.gltf(filepath=str(output / "gallery-kit.glb"), export_format="GLB")


if __name__ == "__main__":
    build(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
