"""Make the last local adjustments to the saved Iuno V4 project."""

import sys
from math import exp, sin, tau
from pathlib import Path
from typing import Any

import bpy  # type: ignore[import-not-found]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.blender_refine_iuno import (  # noqa: E402
    export_and_render,
    front_surface,
    record_settings,
    reshape,
    shape_sections,
)


def refine_expression() -> None:
    objects = bpy.data.objects
    face = objects["Face cushion"]

    def pillow(point: Any) -> tuple[float, float, float]:
        x, y, z = point
        lower_cheek = exp(-(((abs(x) - 0.39) / 0.16) ** 2) - ((z - 1.025) / 0.12) ** 2)
        front = max(0.0, min(1.0, (-y - 0.06) / 0.21))
        chin = max(0.0, min(1.0, (1.085 - z) / 0.21)) ** 2
        return (
            x * (1 + 0.014 * lower_cheek * front),
            y - 0.006 * lower_cheek * front,
            z + 0.008 * chin,
        )

    reshape(face, pillow)
    face_y = front_surface(face)
    for side, sign in (("L", 1), ("R", -1)):
        eye = objects[f"Eye {side} embroidered navy"]

        def place_eye(point: Any, direction: int = sign) -> tuple[float, float, float]:
            x = direction * (0.162 + (direction * point.x - 0.167) * 0.966)
            return x, face_y(x, point.z) - 0.0021, point.z

        reshape(eye, place_eye)
    smile = objects["Stitched smile"]
    reshape(
        smile,
        lambda p: (
            0.957 * p.x,
            face_y(0.957 * p.x, 1.136 + 0.88 * (p.z - 1.136)) - 0.0022,
            1.136 + 0.88 * (p.z - 1.136),
        ),
    )


def refine_hair() -> None:
    objects = bpy.data.objects
    fringe = objects["One-piece embroidered felt fringe"]
    # The existing fringe mesh is organized in columns of 28 vertices.
    rows = 28
    source = [vertex.co.copy() for vertex in fringe.data.vertices]
    for index, vertex in enumerate(fringe.data.vertices):
        row = index % rows
        if row >= 8 or not rows <= index < len(source) - rows:
            continue
        fade = 1 - row / 8
        edge_midpoint = (source[index - rows] + source[index + rows]) * 0.5
        vertex.co = source[index].lerp(edge_midpoint, 0.34 * fade)
        x = vertex.co.x
        lift = 0.006 * exp(-(((x + 0.28) / 0.10) ** 2)) - 0.002 * exp(-(((x - 0.11) / 0.09) ** 2))
        vertex.co.z += lift * fade
    fringe.data.update()
    fringe.modifiers["Felt thickness"].thickness = 0.0125
    fringe.modifiers["Soft cut felt edge"].width = 0.0095

    for side in ("L", "R"):
        for prefix in ("Side felt hair", "Side felt hair tucked layer"):
            obj = objects[f"{prefix} {side}"]
            shape_sections(obj, lambda _i, _n: (1, 0.94, 1))
            reshape(
                obj,
                lambda p: (
                    p.x,
                    p.y + 0.004 * max(0, (1.48 - p.z) / 0.27),
                    p.z + 0.009 * max(0, (1.44 - p.z) / 0.24),
                ),
            )

        def softness(index: int, total: int) -> tuple[float, float, float]:
            t = index / (total - 1)
            fill = 0.017 * exp(-(((t - 0.56) / 0.24) ** 2))
            pinch = 0.016 * exp(-(((t - 0.14) / 0.11) ** 2))
            end = max(0.0, (t - 0.82) / 0.18)
            return 1 + fill - pinch + 0.025 * end, 1 + fill - pinch + 0.012 * end, 1 - 0.017 * end

        shape_sections(objects[f"Long plush ponytail {side}"], softness)
        band = objects[f"Ivory wraparound hair band {side}"]
        center_x = sum(v.co.x for v in band.data.vertices) / len(band.data.vertices)
        for vertex in band.data.vertices:
            angle = tau * (vertex.index // 12) / 48
            vertex.co.x = center_x + (vertex.co.x - center_x) * (1.028 + 0.022 * sin(3 * angle))
        band.data.update()


def refine_clothing() -> None:
    objects = bpy.data.objects
    reshape(
        objects["Uniform torso"], lambda p: (p.x, p.y, p.z + 0.012 * max(0.0, (p.z - 0.75) / 0.15))
    )
    skirt = objects["Pressed ivory pleated skirt"]
    vertices = skirt.data.vertices
    source = [vertex.co.copy() for vertex in vertices]
    for index in range(len(vertices) - 32, len(vertices)):
        column = index % 16
        start = index - column
        neighbor = (source[start + (column - 1) % 16] + source[start + (column + 1) % 16]) * 0.5
        vertices[index].co = source[index].lerp(neighbor, 0.12)
    skirt.data.update()
    for side, sign in (("L", 1), ("R", -1)):
        sleeve = objects[f"Continuous sewn sleeve {side}"]
        for vertex in sleeve.data.vertices:
            section = vertex.index // 16
            if section < 2:
                vertex.co.x -= sign * (0.009 if section == 0 else 0.005)
                vertex.co.z += 0.008 if section == 0 else 0.004
            if section in (5, 6):
                vertex.co.y *= 1.018
        sleeve.data.update()
        for name in (f"White pointed lapel {side}", f"Collar seam {side}"):
            reshape(objects[name], lambda p: (p.x, p.y + 0.002, p.z + 0.006))
        objects[f"White pointed lapel {side}"].modifiers["Soft folded collar edge"].width = 0.004
        jacket = objects[f"Blue jacket front {side}"]
        jacket.modifiers["Jacket fabric thickness"].thickness = 0.0042
        reshape(jacket, lambda p: (p.x, p.y + 0.002 * max(0.0, (0.64 - p.z) / 0.16), p.z))
        for index in range(2):
            seam = objects[f"Skirt blue pleat seam {side} {index}"]
            shape_sections(seam, lambda _i, _n: (0.92, 0.76, 0.88))
        for name in (f"Chocolate slipper {side}", f"Caramel slipper front {side}"):
            reshape(objects[name], lambda p: (p.x, p.y, 0.004 + (p.z - 0.004) * 0.98))
        for slope in (-1, 1):
            stitch = objects[f"Slipper diagonal stitch {side} {slope}"]
            reshape(stitch, lambda p: (p.x, p.y, 0.004 + (p.z - 0.004) * 0.98))


def finish_fabrics(rig: Any) -> None:
    settings = {
        # roughness, specular level, sheen, bump distance
        "Cobalt plush": (0.97, 0.082, 0.16, 0.0075),
        "Navy plush with tint": (0.97, 0.082, 0.16, 0.0075),
        "Warm cream velour": (0.97, 0.084, 0.15, 0.0048),
        "Cream velour with soft blush": (0.97, 0.084, 0.15, 0.0048),
        "Ivory fleece": (0.97, 0.092, 0.21, 0.0078),
        "Ice blue diagonal weave": (0.93, 0.105, 0.11, 0.0055),
        "Warm white diagonal weave": (0.94, 0.095, 0.12, 0.0052),
        "Deep lake eye thread": (0.90, 0.092, 0.13, 0.0042),
        "Pale honey eye thread": (0.90, 0.092, 0.13, 0.0042),
        "Peach pink smile thread": (0.93, 0.090, 0.12, 0.0036),
        "Collar binding": (0.93, 0.095, 0.12, 0.0042),
    }
    for name, (roughness, specular, sheen, bump) in settings.items():
        nodes = bpy.data.materials[name].node_tree.nodes
        shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        shader.inputs["Roughness"].default_value = roughness
        shader.inputs["Specular IOR Level"].default_value = specular
        shader.inputs["Sheen Weight"].default_value = sheen
        next(node for node in nodes if node.type == "BUMP").inputs["Distance"].default_value = bump
    for obj in rig.children:
        nap = obj.modifiers.get("Short stitched plush fibers")
        if nap and obj.name.startswith(
            ("Long plush ponytail", "Ivory wraparound hair band", "Face cushion")
        ):
            density = next(
                socket.identifier
                for socket in nap.node_group.interface.items_tree
                if socket.name == "Density"
            )
            nap[density] *= 1.06


def main(output: Path) -> None:
    if not bpy.data.filepath or Path(bpy.data.filepath).resolve().parent == output:
        raise ValueError("Open the V4 source and choose a separate output directory")
    rig = bpy.data.objects["Iuno"]
    if rig.get("iuno_revision") != "V4.0":
        raise ValueError("This refinement requires the V4.0 source")
    record_settings(output / "v4-before-refinement.json")
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    refine_expression()
    refine_hair()
    refine_clothing()
    finish_fabrics(rig)
    rig["iuno_revision"] = "V4-final"
    export_and_render(output, rig)


if __name__ == "__main__":
    main(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
