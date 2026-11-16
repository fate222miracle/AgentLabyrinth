"""Build the animated GridWorld avatar inside Blender 4.5 LTS."""

import sys
from collections.abc import Callable
from itertools import pairwise
from math import copysign, cos, exp, pi, radians, sin, sqrt
from pathlib import Path
from typing import Any, TypeAlias

import bpy  # type: ignore[import-not-found]
from mathutils import Vector  # type: ignore[import-not-found]
from mathutils.geometry import tessellate_polygon  # type: ignore[import-not-found]

# Blender runs --python with the script directory outside its default import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.blender_key_door_scene import finish, light, material, point_at  # noqa: E402

Point: TypeAlias = tuple[float, float, float]  # noqa: UP040 - Blender 4.5 embeds Python 3.11.


def fit_point(x: float, y: float, z: float, bone: str) -> Point:
    if bone == "Root":
        return x, y, z
    if bone == "Head" or bone.startswith("Hair."):
        return x, 0.895 * y, z - 0.305
    if bone.startswith(("UpperArm.", "Forearm.")):
        sign = 1 if bone.endswith(".L") else -1
        dx, dz = sign * x - 0.24, z - 1.10
        angle = 0.62
        x = sign * (0.24 + dx * cos(angle) - dz * sin(angle))
        z = 1.10 + dx * sin(angle) + dz * cos(angle)
    return 1.08 * x, y, z * 0.70 + min(z / 0.22, 1.0) * 0.04


def make_rig() -> Any:
    data = bpy.data.armatures.new("Iuno skeleton")
    rig = bpy.data.objects.new("Iuno", data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    rig.show_in_front = True
    bpy.ops.object.mode_set(mode="EDIT")

    def bone(name: str, head: Point, tail: Point, parent: str | None = None) -> None:
        segment = data.edit_bones.new(name)
        segment.head, segment.tail = fit_point(*head, name), fit_point(*tail, name)
        if parent:
            segment.parent = data.edit_bones[parent]

    bone("Root", (0, 0, 0), (0, 0, 0.25))
    bone("Torso", (0, 0, 0.67), (0, 0, 1.17), "Root")
    bone("Head", (0, 0, 1.20), (0, 0, 1.85), "Torso")
    for side, sign in (("L", 1), ("R", -1)):
        bone(f"UpperArm.{side}", (sign * 0.24, 0, 1.10), (sign * 0.32, 0, 0.89), "Torso")
        bone(f"Forearm.{side}", (sign * 0.32, 0, 0.89), (sign * 0.35, 0, 0.67), f"UpperArm.{side}")
        bone(f"Thigh.{side}", (sign * 0.12, 0, 0.68), (sign * 0.12, 0, 0.37), "Torso")
        bone(f"Shin.{side}", (sign * 0.12, 0, 0.37), (sign * 0.12, 0, 0.10), f"Thigh.{side}")
        bone(f"Foot.{side}", (sign * 0.12, 0, 0.10), (sign * 0.12, -0.17, 0.06), f"Shin.{side}")
        bone(f"Hair.{side}", (sign * 0.32, 0.16, 1.81), (sign * 0.49, 0.30, 1.40), "Head")
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def model(rig: Any) -> None:
    def fabric(name: str, color: Point, texture: float = 0.12, weave: str = "") -> Any:
        paint = material(name, color)
        nodes = paint.node_tree.nodes
        links = paint.node_tree.links
        shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        shader.inputs["Roughness"].default_value = 0.94 if not weave else 0.84
        shader.inputs["Specular IOR Level"].default_value = 0.20
        shader.inputs["Sheen Weight"].default_value = 0.21 if not weave else 0.14
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 188
        noise.inputs["Detail"].default_value = 2
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = texture
        bump.inputs["Distance"].default_value = 0.010
        height = noise.outputs["Fac"]
        if weave:
            threads = nodes.new("ShaderNodeTexWave")
            threads.bands_direction = weave
            threads.inputs["Scale"].default_value = 34 if weave == "DIAGONAL" else 17
            threads.inputs["Distortion"].default_value = 1.2
            multiply = nodes.new("ShaderNodeMath")
            multiply.operation = "MULTIPLY"
            links.new(height, multiply.inputs[0])
            links.new(threads.outputs["Fac"], multiply.inputs[1])
            height = multiply.outputs[0]
        links.new(height, bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
        return paint

    skin_tone = fabric("Warm cream velour", (0.86, 0.64, 0.48))
    hair = fabric("Cobalt plush", (0.003, 0.024, 0.119), 0.26)
    hair_light = fabric("Cobalt plush tips", (0.004, 0.034, 0.165))
    tint = fabric("Navy plush with tint", (1.0, 1.0, 1.0), 0.26)
    tint_shader = tint.node_tree.nodes.get("Principled BSDF")
    tint_node = tint.node_tree.nodes.new("ShaderNodeVertexColor")
    tint_node.layer_name = "Plush tint"
    tint.node_tree.links.new(tint_node.outputs["Color"], tint_shader.inputs["Base Color"])
    cloud = fabric("Ivory fleece", (0.86, 0.86, 0.79), 0.19)
    shirt = fabric("Warm white diagonal weave", (0.83, 0.85, 0.78), 0.21, "DIAGONAL")
    sky = fabric("Ice blue diagonal weave", (0.19, 0.44, 0.62), 0.21, "DIAGONAL")
    moon_felt = fabric("Pale blue crescent felt", (0.21, 0.55, 0.69), 0.19)
    collar_blue = fabric("Collar binding", (0.11, 0.32, 0.49))
    tie = fabric("Cobalt tie", (0.009, 0.126, 0.341), 0.18, "DIAGONAL")
    embroidery = fabric("Deep lake eye thread", (0.005, 0.071, 0.147), 0.36, "Z")
    gold = fabric("Pale honey eye thread", (0.76, 0.53, 0.19), 0.31, "Z")
    mouth = fabric("Peach pink smile thread", (0.55, 0.17, 0.105), 0.24, "Z")
    boot = fabric("Chocolate shoe", (0.079, 0.019, 0.019))
    toe = fabric("Caramel shoe toe", (0.39, 0.144, 0.037))

    def bind(obj: Any, bone: str, blend: tuple[str, float] | None = None) -> None:
        group = obj.vertex_groups.new(name=bone)
        if blend is None:
            group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        else:
            parent, joint_height = blend
            other = obj.vertex_groups.new(name=parent)
            for vertex in obj.data.vertices:
                weight = min(1.0, max(0.0, (vertex.co.z - joint_height + 0.10) / 0.20))
                group.add([vertex.index], 1.0 - weight, "REPLACE")
                other.add([vertex.index], weight, "REPLACE")
        obj.parent = rig
        obj.modifiers.new("Iuno skeleton", "ARMATURE").object = rig

    def puff(
        name: str,
        center: Point,
        scale: Point,
        paint: Any,
        bone: str,
        power: float = 1,
    ) -> Any:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=center)
        obj = finish(name, paint)
        for vertex in obj.data.vertices:
            for i in range(3):
                v = vertex.co[i]
                vertex.co[i] = (abs(v) ** power if v >= 0 else -(abs(v) ** power)) * scale[i]
        bpy.ops.object.shade_smooth()
        bind(obj, bone)
        return obj

    def mesh_part(
        name: str,
        points: list[Any],
        faces: list[tuple[int, ...]],
        paint: Any,
        bone: str,
        blend: tuple[str, float] | None = None,
    ) -> Any:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(points, [], faces)
        mesh.update()
        mesh.materials.append(paint)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        for poly in mesh.polygons:
            poly.use_smooth = True
        bind(obj, bone, blend)
        return obj

    def loft(
        name: str,
        stations: list[tuple[Point, float, float]],
        paint: Any,
        bone: str,
        *,
        colors: tuple[Any, Any] | None = None,
        blend: tuple[str, float] | None = None,
        stuffing: float = 0,
    ) -> Any:
        centers = [Vector(center) for center, _, _ in stations]
        sides = 16
        points = []
        for i, (center, (_, width, depth)) in enumerate(zip(centers, stations, strict=True)):
            tangent = (centers[min(i + 1, len(centers) - 1)] - centers[max(0, i - 1)]).normalized()
            across = tangent.cross(Vector((0, 1, 0))).normalized()
            normal = across.cross(tangent).normalized()
            progress = i / (len(centers) - 1)
            turn = stuffing * sin(pi * progress)
            across, normal = (
                across * cos(turn) + normal * sin(turn),
                normal * cos(turn) - across * sin(turn),
            )
            for j in range(sides):
                angle = j * 2 * pi / sides
                seam = 1 + abs(stuffing) * sin(pi * progress) * cos(3 * angle + 6 * progress) * 0.24
                points.append(
                    center + seam * (across * (width * cos(angle)) + normal * (depth * sin(angle)))
                )
        faces = [tuple(range(sides))]
        for i in range(len(centers) - 1):
            for j in range(sides):
                a, b = i * sides + j, i * sides + (j + 1) % sides
                faces.append((a, a + sides, b + sides, b))
        faces.append(tuple(reversed(range(len(points) - sides, len(points)))))
        obj = mesh_part(name, points, faces, tint if colors else paint, bone, blend)
        if colors:
            shades = obj.data.color_attributes.new(
                name="Plush tint", type="FLOAT_COLOR", domain="POINT"
            )
            start, end = (Vector(color.diffuse_color) for color in colors)
            for i, sample in enumerate(shades.data):
                sample.color = start.lerp(end, (i // sides) / (len(centers) - 1))
        smooth = obj.modifiers.new("Round sewn edges", "SUBSURF")
        smooth.levels = 2 if colors else 1
        smooth.render_levels = smooth.levels
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_move_up(modifier=smooth.name)
        return obj

    def patch(
        name: str,
        outline: list[tuple[float, float]],
        surface: Callable[[float, float], float],
        paint: Any,
        bone: str,
    ) -> Any:
        # Sample each triangle across its surface so embroidery hugs the cushion.
        flat = [Vector((x, 0, z)) for x, z in outline]
        points: list[Point] = []
        faces: list[tuple[int, ...]] = []
        indices: dict[tuple[tuple[int, int], ...], int] = {}
        steps = 8
        for ai, bi, ci in tessellate_polygon([flat]):
            a, b, c = flat[ai], flat[bi], flat[ci]
            triangle = []
            for i in range(steps + 1):
                for j in range(steps + 1 - i):
                    weights = ((ai, steps - i - j), (bi, i), (ci, j))
                    key = tuple(sorted((index, weight) for index, weight in weights if weight))
                    if key not in indices:
                        p = a.lerp(b, i / steps) + (c - a) * (j / steps)
                        indices[key] = len(points)
                        points.append((p.x, surface(p.x, p.z), p.z))
                    triangle.append(indices[key])
            offset = 0
            for row in range(steps):
                span = steps - row
                for col in range(span):
                    v = offset + col
                    below = v + span + 1
                    faces.append((triangle[v], triangle[below], triangle[v + 1]))
                    if col < span - 1:
                        faces.append((triangle[v + 1], triangle[below], triangle[below + 1]))
                offset += span + 1
        return mesh_part(name, points, faces, paint, bone)

    def face_y(x: float, z: float) -> float:
        curve = abs(x / 0.537) ** 3.45 + abs((z - 1.616) / 0.445) ** 3.45
        return float(-0.023 - 0.327 * max(0.012, 1.0 - curve) ** (1 / 3.45))

    def uniform_y(x: float, z: float) -> float:
        exponent = 2 / 0.79
        inside = 1.0 - abs(x / 0.261) ** exponent - abs((z - 0.82) / 0.353) ** exponent
        return float(-0.166 * max(0.12, inside) ** (1 / exponent))

    def stitch(name: str, points: list[Point], radius: float, paint: Any, bone: str) -> Any:
        return loft(name, [(point, radius, radius) for point in points], paint, bone)

    blushed = skin_tone.copy()
    blushed.name = "Cream velour with soft blush"
    face = puff(
        "Face cushion", (0, -0.023, 1.616), (0.537, 0.327, 0.445), blushed, "Head", 2 / 3.45
    )
    cheeks = face.data.color_attributes.new(name="Cheek tint", type="FLOAT_COLOR", domain="POINT")
    blush = blushed.node_tree.nodes.new("ShaderNodeVertexColor")
    blush.layer_name = cheeks.name
    shader = next(node for node in blushed.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    blushed.node_tree.links.new(blush.outputs["Color"], shader.inputs["Base Color"])
    for vertex, sample in zip(face.data.vertices, cheeks.data, strict=True):
        x, y, z = vertex.co
        strength = 0.26 * exp(-(((abs(x) - 0.281) / 0.091) ** 2) - ((z + 0.16) / 0.066) ** 2)
        weight = strength * max(0.0, min(1.0, -y / 0.22))
        sample.color = Vector(skin_tone.diffuse_color).lerp(Vector((0.80, 0.35, 0.31, 1)), weight)
    # The cap is a curved fabric shell, with the front edge tucked under the bangs.
    cap_center = (0.0, -0.002, 1.64)
    cap_radii = (0.551, 0.364, 0.550)
    cap_power = 0.71
    sections, rows = 64, 30
    cap_points = []
    for section in range(sections):
        azimuth = 2 * pi * section / sections
        back = (1 - cos(azimuth)) * 0.5
        cap_edge = 1.12 + 1.10 * back**0.68
        for row in range(rows):
            fraction = row / (rows - 1)
            polar = 0.024 + (cap_edge - 0.024) * fraction
            surface = (sin(polar) * sin(azimuth), -sin(polar) * cos(azimuth), cos(polar))
            x, y, z = (
                center + radius * copysign(abs(value) ** cap_power, value)
                for center, radius, value in zip(cap_center, cap_radii, surface, strict=True)
            )
            tuck = back * fraction**5
            x *= 1 - 0.02 * tuck
            y -= 0.041 * tuck
            z += 0.013 * tuck
            # Keep the turned cloth edge outside the face mesh after reshaping the cap.
            fullness = (
                abs(x / 0.537) ** 3.45
                + abs((y + 0.023) / 0.327) ** 3.45
                + abs((z - 1.616) / 0.445) ** 3.45
            )
            clearance = max(1.0, (1.06 / fullness) ** (1 / 3.45))
            cap_points.append(
                (x * clearance, -0.023 + (y + 0.023) * clearance, 1.616 + (z - 1.616) * clearance)
            )
    cap_faces: list[tuple[int, ...]] = [tuple(section * rows for section in range(sections))]
    for section in range(sections):
        a, b = section * rows, ((section + 1) % sections) * rows
        for row in range(rows - 1):
            cap_faces.append((a + row, a + row + 1, b + row + 1, b + row))
    cap = mesh_part("Sewn navy hair cap", cap_points, cap_faces, hair, "Head")
    cap.modifiers.new("Turned fabric edge", "SOLIDIFY").thickness = 0.006
    puff("Uniform torso", (0, 0, 0.82), (0.261, 0.166, 0.353), shirt, "Torso", 0.79)
    skirt = loft(
        "Pressed ivory pleated skirt",
        [
            ((0, 0, 0.88), 0.22, 0.14),
            ((0, 0, 0.66), 0.258, 0.163),
            ((0, 0, 0.32), 0.290, 0.182),
            ((0, 0, 0.252), 0.288, 0.176),
        ],
        shirt,
        "Torso",
    )

    def skirt_weights(obj: Any) -> None:
        torso = obj.vertex_groups["Torso"]
        left_thigh = obj.vertex_groups.new(name="Thigh.L")
        right_thigh = obj.vertex_groups.new(name="Thigh.R")
        for vertex in obj.data.vertices:
            follow = min(0.74, max(0.0, (0.66 - vertex.co.z) * 2.2))
            left = min(1.0, max(0.0, 0.5 + vertex.co.x * 5.0))
            torso.add([vertex.index], 1.0 - follow, "REPLACE")
            left_thigh.add([vertex.index], follow * left, "REPLACE")
            right_thigh.add([vertex.index], follow * (1.0 - left), "REPLACE")

    skirt_weights(skirt)

    for side, sign in (("L", 1), ("R", -1)):

        def mirror(
            points: list[tuple[float, float]], sign: int = sign
        ) -> list[tuple[float, float]]:
            return [(sign * x, z) for x, z in (points if sign > 0 else points[::-1])]

        puff(
            f"Peach ear {side}",
            (sign * 0.505, -0.027, 1.53),
            (0.068, 0.10, 0.12),
            skin_tone,
            "Head",
        )
        join = [(0.112, 1.525), (0.146, 1.522), (0.181, 1.524), (0.224, 1.531)]
        top = join + [
            (0.224, 1.574),
            (0.219, 1.610),
            (0.208, 1.642),
            (0.197, 1.652),
            (0.208, 1.669),
            (0.182, 1.665),
            (0.155, 1.667),
            (0.133, 1.655),
            (0.119, 1.635),
            (0.112, 1.604),
            (0.109, 1.563),
        ]
        bottom = [(x, z + 0.006) for x, z in join[::-1]] + [
            (0.216, 1.508),
            (0.204, 1.485),
            (0.190, 1.471),
            (0.172, 1.465),
            (0.154, 1.467),
            (0.138, 1.478),
            (0.126, 1.492),
            (0.116, 1.511),
        ]

        def eye_surface(x: float, z: float) -> float:
            return face_y(x, z) - 0.007

        patch(
            f"Eye {side} embroidered gold",
            mirror(bottom),
            lambda x, z: eye_surface(x, z) + 0.0017,
            gold,
            "Head",
        )
        patch(
            f"Eye {side} embroidered navy",
            mirror(top),
            eye_surface,
            embroidery,
            "Head",
        )

        # Each centerline describes the drape seen on its own side of the plush.
        tail_stations = (
            [
                ((0.47, 0.049, 1.941), 0.084, 0.074),
                ((0.587, 0.069, 1.938), 0.092, 0.087),
                ((0.727, 0.067, 1.852), 0.145, 0.119),
                ((0.847, 0.040, 1.692), 0.196, 0.145),
                ((0.937, -0.010, 1.454), 0.213, 0.144),
                ((0.950, -0.069, 1.233), 0.193, 0.132),
                ((0.905, -0.101, 1.015), 0.204, 0.140),
                ((0.867, -0.122, 0.806), 0.183, 0.122),
                ((0.821, -0.120, 0.676), 0.146, 0.104),
                ((0.805, -0.108, 0.638), 0.086, 0.064),
                ((0.809, -0.103, 0.629), 0.031, 0.030),
            ]
            if sign > 0
            else [
                ((-0.47, 0.034, 1.950), 0.083, 0.076),
                ((-0.592, 0.053, 1.946), 0.100, 0.088),
                ((-0.738, 0.060, 1.870), 0.153, 0.110),
                ((-0.865, 0.040, 1.715), 0.187, 0.134),
                ((-0.931, -0.005, 1.495), 0.203, 0.144),
                ((-0.911, -0.053, 1.294), 0.192, 0.125),
                ((-0.852, -0.098, 1.076), 0.183, 0.123),
                ((-0.837, -0.119, 0.877), 0.201, 0.128),
                ((-0.842, -0.131, 0.722), 0.160, 0.109),
                ((-0.828, -0.129, 0.647), 0.109, 0.075),
                ((-0.805, -0.119, 0.630), 0.036, 0.035),
            ]
        )
        loft(
            f"Long plush ponytail {side}",
            tail_stations,
            hair,
            f"Hair.{side}",
            colors=(hair, hair_light),
            stuffing=0.28 if sign > 0 else -0.32,
        )
        center = Vector((sign * 0.559, 0.055, 1.936))
        axis = Vector((sign * 0.94, 0.030, -0.27)).normalized()
        cross = axis.cross(Vector((0, 1, 0))).normalized()
        around = cross.cross(axis).normalized()
        ring_points = []
        for i in range(48):
            ring_angle = 2 * pi * i / 48
            up = copysign(abs(cos(ring_angle)) ** 0.82, cos(ring_angle))
            radial = (cross * cos(ring_angle) + around * sin(ring_angle)).normalized()
            width = 0.058 + 0.009 * cos(3 * ring_angle + sign) + 0.007 * sin(5 * ring_angle)
            local = center + cross * (0.155 * up) + around * (0.113 * sin(ring_angle))
            fold = 0.066 + 0.009 * cos(2 * ring_angle - sign) + 0.004 * sin(7 * ring_angle)
            for j in range(12):
                section_angle = 2 * pi * j / 12
                ring_points.append(
                    local
                    + radial * (width * cos(section_angle))
                    + axis * (fold * sin(section_angle))
                )
        ring_faces: list[tuple[int, ...]] = []
        for i in range(48):
            for j in range(12):
                a, b = 12 * i + j, 12 * i + (j + 1) % 12
                ring_faces.append((a, b, (b + 12) % 576, (a + 12) % 576))
        mesh_part(
            f"Ivory wraparound hair band {side}", ring_points, ring_faces, cloud, f"Hair.{side}"
        )
        loft(
            f"Side felt hair {side}",
            [
                ((sign * 0.447, -0.235, 1.802), 0.082, 0.039),
                ((sign * 0.465, -0.250, 1.696), 0.084, 0.041),
                ((sign * 0.446, -0.268, 1.602), 0.064, 0.033),
                ((sign * 0.399, -0.288, 1.543), 0.046, 0.024),
                ((sign * 0.388, -0.295, 1.515), 0.009, 0.014),
            ],
            hair,
            "Head",
        )
        loft(
            f"Side felt hair tucked layer {side}",
            [
                ((sign * 0.500, -0.148, 1.747), 0.065, 0.040),
                ((sign * 0.504, -0.165, 1.644), 0.069, 0.038),
                ((sign * 0.493, -0.195, 1.554), 0.057, 0.027),
                ((sign * 0.456, -0.216, 1.501), 0.011, 0.011),
            ],
            hair,
            "Head",
        )

        sleeve = f"UpperArm.{side}"
        forearm = f"Forearm.{side}"
        arm = loft(
            f"Continuous sewn sleeve {side}",
            [
                ((sign * 0.188, 0.005, 1.112), 0.113, 0.118),
                ((sign * 0.224, 0.003, 1.070), 0.119, 0.114),
                ((sign * 0.272, 0, 0.998), 0.105, 0.103),
                ((sign * 0.310, 0, 0.930), 0.092, 0.093),
                ((sign * 0.327, -0.002, 0.869), 0.085, 0.084),
                ((sign * 0.340, -0.005, 0.823), 0.076, 0.078),
                ((sign * 0.346, -0.006, 0.789), 0.073, 0.073),
                ((sign * 0.351, -0.009, 0.758), 0.063, 0.065),
            ],
            sky,
            forearm,
            blend=(sleeve, 0.89),
        )
        arm.data.materials.append(shirt)
        for polygon in arm.data.polygons:
            polygon.material_index = int(polygon.index >= 1 + 4 * 16)
        torso_group = arm.vertex_groups.new(name="Torso")
        upper_group = arm.vertex_groups[sleeve]
        for vertex in arm.data.vertices:
            if vertex.co.z > 1.020:
                hold = min(0.87, (vertex.co.z - 1.020) / 0.108)
                torso_group.add([vertex.index], hold, "REPLACE")
                upper_group.add([vertex.index], 1.0 - hold, "REPLACE")
        puff(
            f"Peach plush mitten {side}",
            (sign * 0.354, -0.017, 0.724),
            (0.071, 0.071, 0.078),
            skin_tone,
            forearm,
            0.74,
        )
        loft(
            f"Padded stocking {side}",
            [
                ((sign * 0.126, 0, 0.654), 0.104, 0.113),
                ((sign * 0.12, 0, 0.385), 0.088, 0.091),
                ((sign * 0.12, -0.010, 0.222), 0.083, 0.094),
                ((sign * 0.12, -0.017, 0.148), 0.083, 0.097),
            ],
            shirt,
            f"Shin.{side}",
            blend=(f"Thigh.{side}", 0.37),
        )
        puff(
            f"Chocolate slipper {side}",
            (sign * 0.131, -0.067, 0.111),
            (0.096, 0.134, 0.104),
            boot,
            f"Foot.{side}",
            0.64,
        )
        puff(
            f"Caramel slipper front {side}",
            (sign * 0.131, -0.157, 0.074),
            (0.079, 0.065, 0.052),
            toe,
            f"Foot.{side}",
            0.84,
        )
        for slope in (-1, 1):
            stitch(
                f"Slipper diagonal stitch {side} {slope}",
                [
                    (sign * 0.131 + dx, y, 0.149 + slope * dz)
                    for dx, y, dz in (
                        (-0.045, -0.191, -0.013),
                        (0.0, -0.203, 0),
                        (0.042, -0.190, 0.013),
                    )
                ],
                0.0038,
                cloud,
                f"Foot.{side}",
            )
        stitch(
            f"Blue sleeve cuff stitching {side}",
            [
                (sign * (0.344 + dx), y, 0.784 + dz)
                for dx, y, dz in (
                    (-0.073, -0.037, 0.016),
                    (-0.034, -0.075, 0.007),
                    (0.020, -0.080, -0.006),
                    (0.070, -0.032, -0.020),
                )
            ],
            0.0035,
            collar_blue,
            forearm,
        )

        panel = [
            (0.074, 1.115),
            (0.218, 1.107),
            (0.266, 1.019),
            (0.248, 0.730),
            (0.187, 0.717),
            (0.103, 0.733),
            (0.063, 0.946),
        ]
        front = patch(
            f"Blue jacket front {side}",
            mirror(panel),
            lambda x, z: uniform_y(x, z) - 0.012,
            sky,
            "Torso",
        )
        front.modifiers.new("Jacket fabric thickness", "SOLIDIFY").thickness = 0.008
        binding = [
            (0.104, 0.733),
            (0.187, 0.717),
            (0.248, 0.730),
            (0.249, 0.763),
            (0.187, 0.748),
            (0.108, 0.764),
        ]
        patch(
            f"White jacket binding {side}",
            mirror(binding),
            lambda x, z: uniform_y(x, z) - 0.022,
            shirt,
            "Torso",
        )
        lapel = [(0.021, 1.118), (0.145, 1.158), (0.213, 1.098), (0.121, 0.981), (0.046, 1.045)]
        collar = patch(
            f"White pointed lapel {side}",
            mirror(lapel),
            lambda x, z: uniform_y(x, z) - 0.037 - 0.10 * (z - 0.98),
            cloud,
            "Torso",
        )
        collar.modifiers.new("Folded collar thickness", "SOLIDIFY").thickness = 0.012
        stitch(
            f"Collar seam {side}",
            [
                (sign * x, uniform_y(sign * x, z) - 0.043 - 0.10 * (z - 0.98), z)
                for x, z in lapel[1:]
            ],
            0.0035,
            collar_blue,
            "Torso",
        )
        for i, start in enumerate((0.078, 0.181)):
            marks = []
            for j, z in enumerate((0.667, 0.51, 0.302)):
                x = sign * (start + (0.020 if i else 0.007) * j)
                width = 0.258 + (0.66 - z) * 0.078
                depth = 0.163 + (0.66 - z) * 0.050
                marks.append((x, -depth * sqrt(1 - (x / width) ** 2) - 0.004, z))
            seam = stitch(
                f"Skirt blue pleat seam {side} {i}",
                marks,
                0.0043,
                collar_blue,
                "Torso",
            )
            skirt_weights(seam)

    smile = [
        (-0.053, 1.447),
        (-0.035, 1.435),
        (-0.018, 1.440),
        (0, 1.433),
        (0.021, 1.440),
        (0.037, 1.436),
        (0.050, 1.453),
    ]
    stitch("Stitched smile", [(x, face_y(x, z) - 0.002, z) for x, z in smile], 0.006, mouth, "Head")

    def fringe_y(x: float, z: float) -> float:
        exponent = 2 / cap_power
        inside = (
            1.0
            - abs(x / cap_radii[0]) ** exponent
            - abs((z - cap_center[2]) / cap_radii[2]) ** exponent
        )
        scalp = float(cap_center[1] - cap_radii[1] * max(0.002, inside) ** (1 / exponent))
        face_front = face_y(x, z)
        fringe_depth = max(0.0, min(1.0, (2.14 - z) / 0.37))
        padding = 0.006 + fringe_depth * (0.010 + 0.007 * cos(15 * x))
        return 0.5 * (scalp + face_front - sqrt((scalp - face_front) ** 2 + 0.0006)) - padding

    hem = [
        (-0.512, 1.748),
        (-0.465, 1.721),
        (-0.418, 1.760),
        (-0.389, 1.703),
        (-0.357, 1.620),
        (-0.301, 1.634),
        (-0.241, 1.661),
        (-0.186, 1.708),
        (-0.148, 1.780),
        (-0.129, 1.724),
        (-0.085, 1.680),
        (-0.027, 1.650),
        (0.057, 1.672),
        (0.127, 1.705),
        (0.191, 1.769),
        (0.222, 1.835),
        (0.251, 1.765),
        (0.286, 1.731),
        (0.339, 1.702),
        (0.397, 1.685),
        (0.420, 1.757),
        (0.476, 1.755),
        (0.513, 1.779),
    ]
    rows = 28
    felt_points = []
    for segment, ((left_x, left_z), (right_x, right_z)) in enumerate(pairwise(hem)):
        for sample in range(6 if segment == len(hem) - 2 else 5):
            ratio = sample / 5
            x = left_x + (right_x - left_x) * ratio
            z_low = left_z + (right_z - left_z) * ratio
            exponent = 2 / cap_power
            z_high = (
                cap_center[2]
                - 0.016
                + cap_radii[2] * (1 - abs(x / cap_radii[0]) ** exponent) ** (1 / exponent)
            )
            for row in range(rows):
                z = z_low + (z_high - z_low) * row / (rows - 1)
                felt_points.append((x, fringe_y(x, z), z))
    felt_faces: list[tuple[int, ...]] = [
        (i + j, i + j + rows, i + j + rows + 1, i + j + 1)
        for i in range(0, len(felt_points) - rows, rows)
        for j in range(rows - 1)
    ]
    bangs = mesh_part("One-piece embroidered felt fringe", felt_points, felt_faces, hair, "Head")
    edge = bangs.modifiers.new("Felt thickness", "SOLIDIFY")
    edge.thickness = 0.018
    edge.offset = 0
    bevel = bangs.modifiers.new("Soft cut felt edge", "BEVEL")
    bevel.width, bevel.segments = 0.008, 3
    loft(
        "Folded top hanging tab",
        [
            ((-0.055, 0.035, 2.172), 0.026, 0.021),
            ((-0.041, 0.044, 2.213), 0.048, 0.019),
            ((0.011, 0.056, 2.218), 0.049, 0.017),
            ((0.049, 0.057, 2.179), 0.022, 0.016),
        ],
        hair,
        "Head",
    )

    tip, moon_base = (0.005, 2.143), (-0.072, 1.910)
    crescent = []
    for arc_start, handle_in, handle_out, arc_end in (
        (tip, (0.179, 2.095), (0.226, 1.871), moon_base),
        (moon_base, (0.091, 1.944), (0.084, 2.051), tip),
    ):
        for i in range(16):
            t = i / 16
            w = 1 - t
            u, v = 3 * w**2 * t, 3 * w * t**2
            x = w**3 * arc_start[0] + u * handle_in[0] + v * handle_out[0] + t**3 * arc_end[0]
            z = w**3 * arc_start[1] + u * handle_in[1] + v * handle_out[1] + t**3 * arc_end[1]
            crescent.append((x, z))
    patch(
        "Sky blue crescent applique",
        crescent,
        lambda x, z: fringe_y(x, z) - 0.013,
        moon_felt,
        "Head",
    )

    necktie = [
        (-0.042, 1.072),
        (0.046, 1.072),
        (0.026, 1.009),
        (0.073, 0.854),
        (0.012, 0.787),
        (-0.055, 0.846),
        (-0.022, 1.007),
    ]
    patch("Blue uniform tie", necktie, lambda x, z: uniform_y(x, z) - 0.022, tie, "Torso")
    for z in (0.916, 0.947):
        patch(
            "Tie pale pinstripe",
            [(-0.034, z + 0.007), (0.045, z), (0.046, z - 0.012), (-0.035, z - 0.006)],
            lambda x, z: uniform_y(x, z) - 0.025,
            sky,
            "Torso",
        )
    puff(
        "Jacket badge",
        (0.198, uniform_y(0.198, 0.899) - 0.014, 0.899),
        (0.021, 0.006, 0.025),
        gold,
        "Torso",
    )

    # Fit each existing part in rig space. Do this after assigning rest-mesh weights.
    for part in rig.children:
        offset = part.location.copy()
        group = part.vertex_groups[0].name
        for vertex in part.data.vertices:
            point = vertex.co + offset
            vertex.co = Vector(fit_point(point.x, point.y, point.z, group)) - offset


def pose_matrix(bone: Any) -> Any:
    rest = bone.bone.matrix_local
    if bone.parent:
        rest = pose_matrix(bone.parent) @ bone.parent.bone.matrix_local.inverted() @ rest
    return rest @ bone.matrix_basis


def aim_pose_bone(bone: Any, target: Point) -> None:
    rest = (
        pose_matrix(bone.parent) @ bone.parent.bone.matrix_local.inverted() @ bone.bone.matrix_local
    )
    local = rest.inverted() @ Vector(target)
    bone.rotation_euler = Vector((0, 1, 0)).rotation_difference(local.normalized()).to_euler()


def animate(rig: Any) -> dict[str, Any]:
    tracks: dict[str, list[tuple[int, dict[str, Point], float]]] = {
        "Idle": [
            (1, {}, 0),
            (25, {"Head": (0, 0, -3), "Hair.L": (6, 0, 0), "Hair.R": (5, 0, 0)}, 0),
            (49, {}, 0),
        ],
        "Walk": [
            (
                1,
                {
                    "Thigh.L": (-24, 0, 0),
                    "Thigh.R": (24, 0, 0),
                    "UpperArm.L": (22, 0, 0),
                    "UpperArm.R": (-22, 0, 0),
                },
                0,
            ),
            (7, {"Shin.R": (36, 0, 0), "Hair.L": (7, 0, 0), "Hair.R": (7, 0, 0)}, 0.023),
            (
                13,
                {
                    "Thigh.L": (24, 0, 0),
                    "Thigh.R": (-24, 0, 0),
                    "UpperArm.L": (-22, 0, 0),
                    "UpperArm.R": (22, 0, 0),
                },
                0,
            ),
            (19, {"Shin.L": (36, 0, 0), "Hair.L": (7, 0, 0), "Hair.R": (7, 0, 0)}, 0.023),
            (
                25,
                {
                    "Thigh.L": (-24, 0, 0),
                    "Thigh.R": (24, 0, 0),
                    "UpperArm.L": (22, 0, 0),
                    "UpperArm.R": (-22, 0, 0),
                },
                0,
            ),
        ],
        "TurnLeft": [
            (1, {}, 0),
            (5, {"Root": (0, 42, 0), "Head": (0, 14, 0), "Thigh.R": (-14, 0, 0)}, 0.018),
            (10, {"Root": (0, 90, 0)}, 0),
        ],
        "TurnRight": [
            (1, {}, 0),
            (5, {"Root": (0, -42, 0), "Head": (0, -14, 0), "Thigh.L": (-14, 0, 0)}, 0.018),
            (10, {"Root": (0, -90, 0)}, 0),
        ],
        "PickUp": [
            (1, {}, 0),
            (
                13,
                {
                    "Torso": (26, 0, 0),
                    "Head": (12, 0, 0),
                    "Thigh.L": (-78, 0, 0),
                    "Thigh.R": (-78, 0, 0),
                    "Shin.L": (100, 0, 0),
                    "Shin.R": (100, 0, 0),
                    "Foot.L": (-48, 0, 0),
                    "Foot.R": (-48, 0, 0),
                },
                -0.21,
            ),
            (22, {}, 0),
            (28, {}, 0),
        ],
        "OpenDoor": [
            (1, {}, 0),
            (11, {"Head": (0, -11, 0)}, 0),
            (17, {}, 0),
            (26, {}, 0),
        ],
    }
    reaches: dict[tuple[str, int], tuple[Point, Point]] = {
        ("PickUp", 13): ((-0.29, -0.12, 0.41), (-0.24, -0.26, 0.26)),
        ("PickUp", 22): ((-0.28, -0.17, 0.75), (-0.19, -0.35, 0.77)),
        ("OpenDoor", 11): ((-0.28, -0.17, 0.83), (-0.22, -0.33, 0.84)),
        ("OpenDoor", 17): ((-0.25, -0.20, 0.84), (-0.17, -0.40, 0.87)),
    }
    animations = rig.animation_data_create()
    actions = {}
    for name, poses in tracks.items():
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        animations.action = action
        for frame, angles, height in poses:
            for bone in rig.pose.bones:
                bone.rotation_mode = "XYZ"
                bone.rotation_euler = tuple(map(radians, angles.get(bone.name, (0, 0, 0))))
            torso = rig.pose.bones["Torso"]
            torso.location.y = height * 0.80
            reach = reaches.get((name, frame))
            if reach:
                elbow, hand = reach
                aim_pose_bone(rig.pose.bones["UpperArm.R"], elbow)
                aim_pose_bone(rig.pose.bones["Forearm.R"], hand)
            for bone in rig.pose.bones:
                bone.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone.name)
            torso.keyframe_insert(data_path="location", frame=frame, group="Torso")
        actions[name] = action
    animations.action = actions["Idle"]
    return actions


def add_short_nap(rig: Any) -> None:
    """Add short render fibers after GLB export so the web model stays light."""
    tree = bpy.data.node_groups.new("Short velour nap", "GeometryNodeTree")
    tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    density = tree.interface.new_socket(
        name="Density", in_out="INPUT", socket_type="NodeSocketFloat"
    )
    length = tree.interface.new_socket(name="Length", in_out="INPUT", socket_type="NodeSocketFloat")
    color = tree.interface.new_socket(
        name="Fiber cloth", in_out="INPUT", socket_type="NodeSocketMaterial"
    )
    tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = tree.nodes, tree.links
    source = nodes.new("NodeGroupInput")
    scatter = nodes.new("GeometryNodeDistributePointsOnFaces")
    direction = nodes.new("ShaderNodeCombineXYZ")
    direction.inputs["X"].default_value = 0.001
    line = nodes.new("GeometryNodeCurvePrimitiveLine")
    profile = nodes.new("GeometryNodeCurvePrimitiveCircle")
    profile.inputs["Resolution"].default_value = 3
    profile.inputs["Radius"].default_value = 0.00031
    fiber = nodes.new("GeometryNodeCurveToMesh")
    paint = nodes.new("GeometryNodeSetMaterial")
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    join = nodes.new("GeometryNodeJoinGeometry")
    output = nodes.new("NodeGroupOutput")
    for node, x, y in (
        (source, -780, 170),
        (scatter, -510, 330),
        (direction, -520, -40),
        (line, -330, -40),
        (profile, -330, -230),
        (fiber, -120, -30),
        (paint, 80, -30),
        (instance, 280, 280),
        (join, 490, 230),
        (output, 680, 230),
    ):
        node.location = x, y
    for start, out_socket, end, in_socket in (
        (source, "Geometry", scatter, "Mesh"),
        (source, "Density", scatter, "Density"),
        (source, "Length", direction, "Z"),
        (direction, "Vector", line, "End"),
        (line, "Curve", fiber, "Curve"),
        (profile, "Curve", fiber, "Profile Curve"),
        (fiber, "Mesh", paint, "Geometry"),
        (source, "Fiber cloth", paint, "Material"),
        (paint, "Geometry", instance, "Instance"),
        (scatter, "Points", instance, "Points"),
        (scatter, "Rotation", instance, "Rotation"),
        (source, "Geometry", join, "Geometry"),
        (instance, "Instances", join, "Geometry"),
        (join, "Geometry", output, "Geometry"),
    ):
        links.new(start.outputs[out_socket], end.inputs[in_socket])

    for part in rig.children:
        name = part.name
        if name.startswith("Ivory wraparound hair band"):
            material_name, count, height = "Ivory fleece", 11500, 0.0048
        elif name == "Face cushion" or name.startswith("Peach ear"):
            material_name, count, height = "Warm cream velour", 10000, 0.0016
        elif name.startswith(
            (
                "Long plush ponytail",
                "Folded plush root tuft",
                "Sewn navy hair cap",
                "Side felt hair",
                "One-piece embroidered",
            )
        ):
            material_name, count, height = "Cobalt plush", 10500, 0.0033
        else:
            continue
        modifier = part.modifiers.new("Short stitched plush fibers", "NODES")
        modifier.node_group = tree
        modifier[density.identifier] = float(count)
        modifier[length.identifier] = height
        modifier[color.identifier] = bpy.data.materials[material_name]


def build(output: Path) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    rig = make_rig()
    model(rig)
    animate(rig)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_end = 49
    scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (rig, *rig.children):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(output / "iuno-chibi.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_animation_mode="ACTIONS",
        export_anim_single_armature=True,
    )
    add_short_nap(rig)

    world_tree = scene.world.node_tree
    world = next(node for node in world_tree.nodes if node.type == "BACKGROUND")
    world.inputs["Color"].default_value = (0.44, 0.45, 0.47, 1.0)
    world.inputs["Strength"].default_value = 0.30
    camera_background = world_tree.nodes.new("ShaderNodeBackground")
    camera_background.inputs["Color"].default_value = (0.47, 0.465, 0.45, 1.0)
    camera_background.inputs["Strength"].default_value = 0.82
    ray = world_tree.nodes.new("ShaderNodeLightPath")
    mix = world_tree.nodes.new("ShaderNodeMixShader")
    target = next(node for node in world_tree.nodes if node.type == "OUTPUT_WORLD")
    world_tree.links.new(ray.outputs["Is Camera Ray"], mix.inputs[0])
    world_tree.links.new(world.outputs["Background"], mix.inputs[1])
    world_tree.links.new(camera_background.outputs["Background"], mix.inputs[2])
    world_tree.links.new(mix.outputs["Shader"], target.inputs["Surface"])
    sweep = [
        (-9.0, 0),
        (1.7, 0),
        (2.4, 0.04),
        (2.85, 0.18),
        (3.17, 0.43),
        (3.39, 0.77),
        (3.52, 1.2),
        (3.55, 3.0),
        (3.55, 8.0),
    ]
    background = bpy.data.meshes.new("Neutral studio sweep")
    corners = [(x, y, z - 0.004) for y, z in sweep for x in (-18, 18)]
    background.from_pydata(
        corners, [], [(i, i + 1, i + 3, i + 2) for i in range(0, len(corners) - 2, 2)]
    )
    for polygon in background.polygons:
        polygon.use_smooth = True
    backdrop = bpy.data.objects.new(background.name, background)
    bpy.context.collection.objects.link(backdrop)
    backdrop.data.materials.append(material("Neutral gray studio", (0.44, 0.43, 0.41)))
    backdrop.visible_camera = False
    cameras = {}
    diagonal = 6.7 / sqrt(2)
    for name, filename, location in (
        ("Front orthographic", "preview.png", (0, -6.7, 0.98)),
        ("Left 45 orthographic", "left-preview.png", (-diagonal, -diagonal, 0.98)),
        ("Right 45 orthographic", "grid-preview.png", (diagonal, -diagonal, 0.98)),
        ("Right 90 orthographic", "side-preview.png", (6.7, 0, 0.98)),
    ):
        data = bpy.data.cameras.new(name)
        data.type, data.ortho_scale = "ORTHO", 2.61
        camera = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(camera)
        camera.location = location
        point_at(camera, (0, 0, 0.98))
        cameras[filename] = camera
    scene.camera = cameras["preview.png"]
    light("Softbox", (-2.8, -3.5, 4.2), 480, 4.4)
    light("Fill", (2.6, -3.0, 2.6), 220, 4.0)
    light("Fiber rim", (0, 1.9, 3.4), 190, 3.0)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 18
    scene.cycles.adaptive_threshold = 0.033
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 800, 836
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output / "preview.png")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.shading.color_type = "MATERIAL"
                area.spaces.active.overlay.show_overlays = False
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "iuno-chibi.blend"))
    for name, camera in cameras.items():
        scene.camera = camera
        scene.render.filepath = str(output / name)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build(Path(sys.argv[sys.argv.index("--") + 1]).resolve(strict=True))
