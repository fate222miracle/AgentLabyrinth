"""Check the animated avatar export before using it in GridWorld."""

import json
import struct
import sys
from pathlib import Path

CLIPS = {"Idle", "Walk", "TurnLeft", "TurnRight", "PickUp", "OpenDoor"}


def check(path: Path) -> None:
    raw = path.read_bytes()
    assert struct.unpack_from("<4sII", raw) == (b"glTF", 2, len(raw))
    json_size, json_tag = struct.unpack_from("<I4s", raw, 12)
    assert json_tag == b"JSON"
    end = 20 + json_size
    gltf = json.loads(raw[20:end])
    assert len(gltf["skins"]) == 1 and len(gltf["skins"][0]["joints"]) == 15
    assert len(gltf["animations"]) == len(CLIPS)
    assert {clip["name"] for clip in gltf["animations"]} == CLIPS
    root = next(i for i, node in enumerate(gltf["nodes"]) if node.get("name") == "Root")
    for clip in gltf["animations"]:
        assert len(clip["channels"]) > 0
        for channel in clip["channels"]:
            if channel["target"] != {"node": root, "path": "translation"}:
                continue
            output = clip["samplers"][channel["sampler"]]["output"]
            accessor = gltf["accessors"][output]
            assert accessor["type"] == "VEC3" and accessor["componentType"] == 5126
            view = gltf["bufferViews"][accessor["bufferView"]]
            offset = end + 8 + view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
            stride = view.get("byteStride", 12)
            for index in range(accessor["count"]):
                assert not any(struct.unpack_from("<3f", raw, offset + index * stride))
    assert any(
        "COLOR_0" in primitive["attributes"]
        for mesh in gltf["meshes"]
        for primitive in mesh["primitives"]
    ), "Hair gradient colors are missing"


if __name__ == "__main__":
    check(Path(sys.argv[1]))
    print("Verified six clips, 15 joints, stationary root and hair gradient.")
