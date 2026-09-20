"""Load the verified local BFCL subset into existing platform contracts."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, JsonValue, create_model

from packages.domain.models import TaskSpec, ToolSchema

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / "benchmarks/bfcl_adapted/dataset_manifest.json"
DEFAULT_SUBSET = ROOT / ".cache/bfcl/subset.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python_type(schema: dict[str, Any], name: str) -> Any:
    kind = schema.get("type")
    if kind == "integer":
        return int
    if kind == "number":
        return float
    if kind == "boolean":
        return bool
    if kind == "array":
        return list[Any]
    if kind == "object":
        return model_from_schema(schema, name)
    return str


def model_from_schema(schema: dict[str, Any], name: str) -> type[BaseModel]:
    """Build a strict Pydantic model for the selected BFCL JSON Schema subset."""
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    for field_name, field_schema in schema.get("properties", {}).items():
        field_type = _python_type(field_schema, f"{name}{field_name.title()}")
        fields[field_name] = (field_type, ...) if field_name in required else (field_type, None)
    return create_model(
        re.sub(r"\W+", "_", name),
        __config__=ConfigDict(strict=True, extra="forbid"),
        **fields,
    )


class BFCLCase(BaseModel):
    """One locally adapted, non-executable BFCL single-call case."""

    model_config = ConfigDict(frozen=True)
    id: str
    split: str
    question: str
    tool: dict[str, Any]
    ground_truth: dict[str, dict[str, list[JsonValue]]]

    @property
    def tool_name(self) -> str:
        return str(self.tool["name"])

    def tool_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.tool_name,
            description=str(self.tool.get("description", "")),
            parameters=self.tool_parameters,
            version="bfcl-v4-pinned",
            risk_level="READ_ONLY",
        )

    def argument_model(self) -> type[BaseModel]:
        return model_from_schema(cast(dict[str, Any], self.tool["parameters"]), self.tool_name)

    @property
    def tool_parameters(self) -> dict[str, JsonValue]:
        """Return JSON-compatible parameters from the validated source case."""
        return cast(dict[str, JsonValue], self.tool["parameters"])

    def task_spec(self, manifest: dict[str, Any], manifest_hash: str) -> TaskSpec:
        return TaskSpec(
            id=uuid5(NAMESPACE_URL, f"agentlabyrinth:bfcl:{self.id}"),
            name=f"bfcl-{self.id}",
            version="1.0.0",
            category="bfcl_single_call",
            description=self.question,
            initial_state={"source_case_id": self.id},
            goal_conditions={"expected_call": cast(JsonValue, self.ground_truth)},
            constraints=("Propose exactly one tool call.",),
            expected_tools=(self.tool_name,),
            max_steps=1,
            token_budget=8000,
            evaluator_config={
                "name": manifest["evaluator_version"],
                "suite": "bfcl_adapted",
                "split": self.split,
                "origin": "external_reference",
                "source_commit": manifest["source_version_or_commit"],
                "source_case_id": self.id,
                "manifest_sha256": manifest_hash,
                "subset_sha256": manifest["checksum"],
                "adapter_version": manifest["adapter_version"],
                "result_label": manifest["result_label"],
            },
        )


class BFCLAdapter:
    """Verify manifest and transformed cache before exposing selected cases."""

    def __init__(
        self, manifest_path: Path = DEFAULT_MANIFEST, subset_path: Path = DEFAULT_SUBSET
    ) -> None:
        self.manifest_path = manifest_path
        self.subset_path = subset_path

    def load(self) -> tuple[dict[str, Any], dict[str, BFCLCase]]:
        """Load only a checksum-verified transformed cache."""
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not self.subset_path.is_file():
            raise FileNotFoundError("BFCL cache missing; run scripts/import_bfcl_subset.py")
        if _sha256(self.subset_path) != manifest["checksum"]:
            raise ValueError("BFCL transformed subset checksum mismatch")
        raw_cases = json.loads(self.subset_path.read_text(encoding="utf-8"))
        cases = {case.id: case for case in map(BFCLCase.model_validate, raw_cases)}
        selected = {case_id for ids in manifest["selected_cases"].values() for case_id in ids}
        if set(cases) != selected:
            raise ValueError("BFCL selected case IDs do not match the manifest")
        return manifest, cases

    def tasks(self) -> list[TaskSpec]:
        manifest, cases = self.load()
        manifest_hash = _sha256(self.manifest_path)
        return [cases[case_id].task_spec(manifest, manifest_hash) for case_id in sorted(cases)]

    def case_for_task(self, task_id: str) -> tuple[BFCLCase, TaskSpec]:
        manifest, cases = self.load()
        for case in cases.values():
            task = case.task_spec(manifest, _sha256(self.manifest_path))
            if task_id in (case.id, task.name, str(task.id)):
                return case, task
        raise ValueError("BFCL task not found in the pinned manifest")
