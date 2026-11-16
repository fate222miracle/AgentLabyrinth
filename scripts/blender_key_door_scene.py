"""Build a reusable GridWorld asset sample inside Blender's Python process."""

import sys
from pathlib import Path
from typing import Any

import bpy  # type: ignore[import-not-found]
from mathutils import Vector  # type: ignore[import-not-found]


def material(name: str, color: tuple[float, float, float], metallic: float = 0) -> Any:
    surface = bpy.data.materials.new(name)
    surface.diffuse_color = (*color, 1)
    surface.use_nodes = True
    shader = surface.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = 0.38
    return surface


def finish(name: str, surface: object) -> Any:
    mesh = bpy.context.object
    mesh.name = name
    mesh.data.materials.append(surface)
    return mesh


def box(
    name: str,
    at: tuple[float, float, float],
    size: tuple[float, float, float],
    surface: object,
    bevel: float = 0.035,
) -> None:
    bpy.ops.mesh.primitive_cube_add(size=1, location=at)
    mesh = bpy.context.object
    mesh.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = mesh.modifiers.new("Rounded edges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    mesh.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    finish(name, surface)


def sphere(name: str, at: tuple[float, float, float], radius: float, surface: object) -> None:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=at)
    finish(name, surface)
    bpy.ops.object.shade_smooth()


def point_at(obj: Any, point: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def light(name: str, at: tuple[float, float, float], energy: float, size: float) -> None:
    source = bpy.data.lights.new(name, "AREA")
    source.energy, source.shape, source.size = energy, "DISK", size
    obj = bpy.data.objects.new(name, source)
    bpy.context.collection.objects.link(obj)
    obj.location = at
    point_at(obj, (0, 0, 0))


def build(output: Path) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    base = material("Ink", (0.022, 0.045, 0.065))
    tile = material("Mist blue", (0.19, 0.31, 0.36))
    tile_light = material("Frost", (0.24, 0.38, 0.41))
    wall = material("Deep slate", (0.055, 0.12, 0.16))
    gold = material("Brass", (0.83, 0.37, 0.055), metallic=0.55)
    door = material("Oxide red", (0.48, 0.095, 0.046))
    green = material("Jade", (0.09, 0.62, 0.39))
    cream = material("Ivory", (0.88, 0.76, 0.53))
    box("Foundation", (0, 0, -0.22), (5.28, 3.28, 0.28), base, 0.09)
    for row in range(-1, 2):
        for column in range(-2, 3):
            box(
                f"Floor {column} {row}",
                (column, row, -0.055),
                (0.96, 0.96, 0.11),
                tile if (column + row) % 2 else tile_light,
            )
    for column in (-2, -1, 0, 1, 2):
        box(f"Wall {column}", (column, 1, 0.22), (0.96, 0.82, 0.44), wall)
    for side in (-0.43, 0.43):
        box("Door jamb", (0, side, 0.60), (0.17, 0.13, 1.20), gold)
    box("Door lintel", (0, 0, 1.20), (0.20, 1.02, 0.13), gold)
    box("Door panel", (0, 0, 0.54), (0.12, 0.72, 1.03), door)
    sphere("Door handle", (0.085, -0.23, 0.53), 0.07, gold)
    bpy.ops.mesh.primitive_torus_add(
        major_segments=32,
        minor_segments=12,
        location=(-1.47, 0, 0.18),
        major_radius=0.14,
        minor_radius=0.045,
    )
    finish("Key bow", gold)
    box("Key shaft", (-1.20, 0, 0.18), (0.33, 0.07, 0.075), gold, 0.012)
    box("Key tooth", (-1.08, -0.065, 0.18), (0.07, 0.13, 0.075), gold, 0.012)
    box("Goal tile", (2, 0, 0.05), (0.8, 0.8, 0.10), green, 0.08)
    bpy.ops.mesh.primitive_torus_add(
        major_segments=32,
        minor_segments=12,
        location=(2, 0, 0.34),
        rotation=(1.5708, 0, 0),
        major_radius=0.24,
        minor_radius=0.043,
    )
    finish("Goal marker", green)
    box("Agent body", (-2, -0.74, 0.26), (0.33, 0.27, 0.39), cream, 0.075)
    sphere("Agent head", (-2, -0.74, 0.53), 0.20, cream)
    for side in (-0.07, 0.07):
        sphere("Agent eye", (-2 + side, -0.915, 0.55), 0.035, base)

    scene = bpy.context.scene
    scene.world.color = (0.13, 0.13, 0.13)
    bpy.ops.object.camera_add(location=(5.8, -8.2, 6.5))
    camera = bpy.context.object
    point_at(camera, (0, 0, 0.12))
    camera.data.type, camera.data.ortho_scale = "ORTHO", 7.4
    scene.camera = camera
    light("Key light", (2, -3.5, 6.5), 800, 5)
    light("Fill light", (-4, 0, 4), 460, 4)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 960, 560
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output / "preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "key-door.blend"))
    bpy.ops.export_scene.gltf(filepath=str(output / "key-door.glb"), export_format="GLB")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
