"""Fake ModelProvider implementation for deterministic testing and M0 execution."""

import re
from decimal import Decimal
from typing import Any

from packages.domain.models import (
    EstimatedCost,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    TokenUsage,
    ToolCall,
    ToolCallBatch,
    ToolSchema,
)
from packages.domain.ports import ModelProvider


class FakeModelProvider(ModelProvider):
    """Fake model provider translating public observation to portable responses."""

    def __init__(
        self,
        scenario: str = "normal",
        custom_responses: list[ModelResponse] | None = None,
        initial_call_count: int = 0,
    ) -> None:
        self.scenario = scenario.replace("-", "_")
        self.custom_responses = list(custom_responses) if custom_responses else []
        if initial_call_count < 0:
            raise ValueError("initial_call_count must be non-negative")
        self._call_count = initial_call_count

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Return a validated action based on public messages and scenario."""
        messages = self._visible_memory(messages)
        self._call_count += 1

        if self.custom_responses:
            index = min(self._call_count - 1, len(self.custom_responses) - 1)
            return self.custom_responses[index].model_copy(deep=True)

        token_usage = TokenUsage(prompt_tokens=40, completion_tokens=20, simulated=True)
        estimated_cost = EstimatedCost(
            amount=Decimal("0.001"),
            currency="USD",
            price_table_version="fake-zero-v1",
            estimated=True,
        )

        if self.scenario == "unparseable":
            raise ValueError("FakeModelProvider simulated unparseable model response")
        if self.scenario == "final_answer_only":
            return ModelResponse(
                action=FinalAnswer(text="Task solved without tool submission."),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )
        if self.scenario == "forbidden_tool":
            return ModelResponse(
                action=ToolCall(
                    call_id="call_forb_1",
                    name="unregistered_or_forbidden",
                    arguments={"key": "val"},
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )
        if self.scenario == "duplicate_call_id":
            return ModelResponse(
                action=ToolCall(
                    call_id="duplicate_id_001",
                    name="query_records",
                    arguments={"table": "orders", "filters": {"order_id": "ORD-001"}},
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )

        kind = self._extract_task_kind(messages)
        if kind == "document_route":
            if any(tool.name == "update_plan" for tool in tools) and not self._plan_visible(
                messages
            ):
                return self._plan_response(token_usage, estimated_cost, routing=True)
            return self._route_response(
                messages, token_usage, estimated_cost, batch_reads=config.tool_call_mode == "serial"
            )
        if kind in ("document_rule", "document_plan"):
            plan_tool = any(tool.name == "update_plan" for tool in tools)
            return self._rule_response(
                messages,
                token_usage,
                estimated_cost,
                batch_reads=config.tool_call_mode == "serial",
                emit_plan=(
                    kind == "document_plan" and plan_tool and not self._plan_visible(messages)
                ),
            )
        if kind == "document_chain":
            return self._chain_response(messages, token_usage, estimated_cost)
        if kind == "document":
            return self._document_response(messages, token_usage, estimated_cost)

        if self.scenario == "invalid_arguments":
            return self._invalid_order_response(token_usage, estimated_cost)
        if self.scenario == "invalid_then_success" and self._call_count == 1:
            return self._invalid_order_response(token_usage, estimated_cost)

        query_result = self._extract_query_result(messages)
        if self.scenario in {"max_steps", "looping"}:
            target_order_id = self._extract_target_order_id(messages)
            return ModelResponse(
                action=ToolCall(
                    call_id=f"call_loop_{self._call_count}",
                    name="query_records",
                    arguments={
                        "table": "orders",
                        "filters": {"order_id": target_order_id},
                    },
                ),
                token_usage=token_usage,
                estimated_cost=estimated_cost,
            )

        if query_result is None:
            target_order_id = self._extract_target_order_id(messages)
            action = ToolCall(
                call_id=f"call_query_{self._call_count}",
                name="query_records",
                arguments={
                    "table": "orders",
                    "filters": {"order_id": target_order_id},
                },
            )
        else:
            answer = (
                "processing"
                if self.scenario in {"wrong-answer", "wrong_answer"}
                else query_result["status"]
            )
            action = ToolCall(
                call_id=f"call_submit_{self._call_count}",
                name="submit_answer",
                arguments={"answer": answer, "evidence": query_result["evidence"]},
            )
        return ModelResponse(
            action=action,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def _visible_memory(messages: list[Message]) -> list[Message]:
        """Interpret only the explicit public memory envelope, like visible tool feedback."""
        expanded: list[Message] = []
        for message in messages:
            expanded.append(message)
            if message.role != "user" or not isinstance(message.content, dict):
                continue
            memory = message.content.get("_agentlabyrinth_memory")
            if not isinstance(memory, dict) or memory.get("schema_version") != "1.0":
                continue
            entries = memory.get("entries")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                observation, call_id = entry.get("observation"), entry.get("call_id")
                if (
                    isinstance(observation, dict)
                    and "result" in observation
                    and "error" not in observation
                    and isinstance(call_id, str)
                ):
                    expanded.append(Message(role="tool", content=observation, tool_call_id=call_id))
        return expanded

    def _invalid_order_response(
        self, token_usage: TokenUsage, estimated_cost: EstimatedCost
    ) -> ModelResponse:
        """Return the deterministic malformed order query used by recovery tests."""
        return ModelResponse(
            action=ToolCall(
                call_id=f"call_inv_{self._call_count}",
                name="query_records",
                arguments={"table": "invalid_table", "filters": {}},
            ),
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

    def _extract_task_kind(self, messages: list[Message]) -> str:
        """Read public task mode without inspecting private goal conditions."""
        for msg in messages:
            if isinstance(msg.content, dict) and msg.content.get("task_kind") in (
                "document",
                "document_chain",
                "document_rule",
                "document_plan",
                "document_route",
            ):
                return str(msg.content["task_kind"])
        return "order"

    @staticmethod
    def _plan_visible(messages: list[Message]) -> bool:
        """The declared plan is re-injected under this reserved key once it is recorded."""
        return any(
            isinstance(message.content, dict) and "_agentlabyrinth_plan" in message.content
            for message in messages
        )

    def _plan_response(
        self, usage: TokenUsage, cost: EstimatedCost, *, routing: bool = False
    ) -> ModelResponse:
        """Declare a bounded, acyclic plan once; a declaration, never verified execution."""
        return ModelResponse(
            action=ToolCall(
                call_id=f"call_plan_{self._call_count}",
                name="update_plan",
                arguments={
                    "plan": [
                        {
                            "id": "facts",
                            "goal": (
                                "读取登记与验收，按通道选择政策并完成全部适用核验。"
                                if routing
                                else "Read the registration, inspection, and applicable policy "
                                "documents for received/damaged/required units."
                            ),
                            "status": "active",
                            "depends_on": [],
                        },
                        {
                            "id": "decide",
                            "goal": (
                                "依据可用件数和适用核验结果提交结论与完整实际证据。"
                                if routing
                                else "Compute usable_units = received - damaged "
                                "and submit the status "
                                "with the three evidence ids."
                            ),
                            "status": "pending",
                            "depends_on": ["facts"],
                        },
                    ]
                },
            ),
            token_usage=usage,
            estimated_cost=cost,
        )

    @staticmethod
    def _visible_documents(messages: list[Message]) -> dict[str, dict[str, str]]:
        """Collect public document returns, rejecting inconsistent versions of an ID."""
        documents: dict[str, dict[str, str]] = {}
        for message in messages:
            content = message.content
            if message.role != "tool" or not isinstance(content, dict):
                continue
            result = content.get("result")
            doc = result.get("document") if isinstance(result, dict) else None
            if not isinstance(doc, dict) or not all(
                isinstance(doc.get(key), str) for key in ("document_id", "content", "evidence_id")
            ):
                continue
            parsed = {key: str(doc[key]) for key in ("document_id", "content", "evidence_id")}
            previous = documents.get(parsed["document_id"])
            if previous is not None and previous != parsed:
                raise ValueError("Conflicting visible document versions")
            documents[parsed["document_id"]] = parsed
        return documents

    @staticmethod
    def _route_fields(body: str) -> dict[str, str]:
        """Read the finite conditional-eligibility-v1 markers, never execute text."""
        fields: dict[str, str] = {}
        references = {
            "Inspection document",
            "Route standard",
            "Route restricted",
            "Approval document",
            "Damage review document",
        }
        for line in body.splitlines():
            if line.startswith("Fact:"):
                match = re.fullmatch(
                    r"Fact: (lane|received_units|damaged_units|required_units|approved)=(.+)", line
                )
                if match is None:
                    raise ValueError("Invalid route fact")
                key, value = match.groups()
            else:
                key, separator, value = line.partition(": ")
                if key not in references | {"Workflow"}:
                    if any(line.startswith(marker + ":") for marker in references | {"Workflow"}):
                        raise ValueError("Malformed route field")
                    continue
                if not separator or not value:
                    raise ValueError("Missing route field")
            if key in fields:
                raise ValueError("Duplicate route field")
            if key in references and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                raise ValueError("Invalid route document reference")
            if key in {"received_units", "damaged_units", "required_units"} and (
                not re.fullmatch(r"[0-9]{1,7}", value) or int(value) > 1_000_000
            ):
                raise ValueError("Invalid route quantity")
            if key == "lane" and value not in {"standard", "restricted"}:
                raise ValueError("Invalid route lane")
            if key == "approved" and value not in {"true", "false"}:
                raise ValueError("Invalid route approval")
            if key == "Workflow" and value != "conditional-eligibility-v1":
                raise ValueError("Unsupported route workflow")
            fields[key] = value
        return fields

    def _route_response(
        self, messages: list[Message], usage: TokenUsage, cost: EstimatedCost, *, batch_reads: bool
    ) -> ModelResponse:
        """Follow visible references and conditional checks; private task goals are unavailable."""
        documents = self._visible_documents(
            [m for m in messages if not isinstance(m.content, dict) or "error" not in m.content]
        )
        fields = {id_: self._route_fields(doc["content"]) for id_, doc in documents.items()}

        def act(name: str, arguments: dict[str, Any]) -> ModelResponse:
            return ModelResponse(
                action=ToolCall(
                    call_id=f"call_route_{self._call_count}", name=name, arguments=arguments
                ),
                token_usage=usage,
                estimated_cost=cost,
            )

        def read(targets: list[str]) -> ModelResponse:
            if batch_reads and len(targets) > 1:
                return ModelResponse(
                    schema_version="1.1",
                    action=ToolCallBatch(
                        calls=tuple(
                            ToolCall(
                                call_id=f"call_route_{self._call_count}_{i}",
                                name="read_document",
                                arguments={"document_id": target},
                            )
                            for i, target in enumerate(dict.fromkeys(targets))
                        )
                    ),
                    token_usage=usage,
                    estimated_cost=cost,
                )
            return act("read_document", {"document_id": targets[0]})

        def required(id_: str, keys: set[str]) -> dict[str, str]:
            data = fields[id_]
            if not keys <= data.keys():
                raise ValueError("Missing required route fields")
            return data

        roots = [id_ for id_, data in fields.items() if "Workflow" in data]
        if len(roots) > 1:
            raise ValueError("Ambiguous route registration")
        if not roots:
            first = self._extract_document_search_result(messages)
            if first in documents:
                raise ValueError("Missing route workflow")
            return (
                read([first])
                if first
                else act(
                    "search_documents",
                    {"query": self._extract_document_query(messages), "top_k": 3},
                )
            )
        registration = roots[0]
        root = required(registration, {"Inspection document", "Route standard", "Route restricted"})
        inspection = root["Inspection document"]
        if inspection not in fields:
            return read([inspection])
        facts = required(inspection, {"lane", "received_units", "damaged_units"})
        received, damaged = int(facts["received_units"]), int(facts["damaged_units"])
        if damaged > received:
            raise ValueError("Damaged quantity exceeds received quantity")
        policy = root[f"Route {facts['lane']}"]
        if policy not in fields:
            return read([policy])
        rule = required(policy, {"required_units"})
        checks = list(
            dict.fromkeys(
                rule[key]
                for key in ("Approval document", "Damage review document")
                if key in rule and (key != "Damage review document" or damaged > 0)
            )
        )
        missing = [id_ for id_ in checks if id_ not in fields]
        if missing:
            return read(missing)
        approved = [required(id_, {"approved"})["approved"] == "true" for id_ in checks]
        eligible = received - damaged >= int(rule["required_units"]) and all(approved)
        return act(
            "submit_answer",
            {
                "answer": "eligible" if eligible else "ineligible",
                "evidence": sorted(
                    {
                        documents[id_]["evidence_id"]
                        for id_ in [registration, inspection, policy, *checks]
                    }
                ),
            },
        )

    def _rule_response(
        self,
        messages: list[Message],
        usage: TokenUsage,
        cost: EstimatedCost,
        *,
        batch_reads: bool = False,
        emit_plan: bool = False,
    ) -> ModelResponse:
        """Apply one public units rule to visible facts; missing facts require actual reads."""
        if emit_plan:
            return self._plan_response(usage, cost)
        documents = self._visible_documents(messages)

        facts: dict[str, dict[str, str]] = {}
        sources: dict[str, str] = {}
        policies: dict[str, str] = {}
        rule_seen = False
        for id_, visible_doc in documents.items():
            fields: dict[str, str] = {}
            for key, value in re.findall(
                r"^Fact: (received_units|damaged_units|required_units|policy_revision)="
                r"([A-Za-z0-9-]+)$",
                visible_doc["content"],
                re.MULTILINE,
            ):
                if key in fields and fields[key] != value:
                    raise ValueError("Conflicting visible facts")
                if key != "policy_revision" and (not value.isdecimal() or int(value) > 1_000_000):
                    raise ValueError("Invalid visible quantity")
                fields[key] = value
            facts[id_] = fields
            for key, target in re.findall(
                r"^Source (received_units|damaged_units|required_units): ([A-Za-z0-9_-]+)$",
                visible_doc["content"],
                re.MULTILINE,
            ):
                if key in sources and sources[key] != target:
                    raise ValueError("Conflicting public source references")
                sources[key] = target
            for revision, target in re.findall(
                r"^Policy document: ([A-Za-z0-9-]+)=([A-Za-z0-9_-]+)$",
                visible_doc["content"],
                re.MULTILINE,
            ):
                if revision in policies and policies[revision] != target:
                    raise ValueError("Conflicting public policy references")
                policies[revision] = target
            rules = re.findall(r"^Rule: (.+)$", visible_doc["content"], re.MULTILINE)
            if any(rule != "usable-units-v1" for rule in rules):
                raise ValueError("Unsupported public rule")
            rule_seen = rule_seen or bool(rules)

        def one(key: str, revision: str | None = None) -> str | None:
            matches = [
                id_
                for id_, fields in facts.items()
                if key in fields and (revision is None or fields.get("policy_revision") == revision)
            ]
            if len(matches) > 1:
                raise ValueError("Ambiguous visible fact sources")
            return matches[0] if matches else None

        intake = one("received_units")
        inspection = one("damaged_units")
        revision = facts[intake].get("policy_revision") if intake else None
        policy = one("required_units", revision) if revision else None
        if batch_reads and intake and revision:
            targets = []
            if not inspection or not rule_seen:
                targets.append(sources.get("damaged_units"))
            if not policy:
                targets.append(policies.get(revision) or sources.get("required_units"))
            targets = list(dict.fromkeys(t for t in targets if t))
            if len(targets) > 1:
                return ModelResponse(
                    schema_version="1.1",
                    action=ToolCallBatch(
                        calls=tuple(
                            ToolCall(
                                call_id=f"call_rule_{self._call_count}_{i}",
                                name="read_document",
                                arguments={"document_id": target},
                            )
                            for i, target in enumerate(targets)
                        )
                    ),
                    token_usage=usage,
                    estimated_cost=cost,
                )
        if intake and inspection and policy and rule_seen:
            received = int(facts[intake]["received_units"])
            damaged = int(facts[inspection]["damaged_units"])
            required = int(facts[policy]["required_units"])
            if damaged > received:
                raise ValueError("Damaged quantity exceeds received quantity")
            name = "submit_answer"
            arguments: dict[str, Any] = {
                "answer": "eligible" if received - damaged >= required else "ineligible",
                "evidence": sorted(
                    {documents[id_]["evidence_id"] for id_ in (intake, inspection, policy)}
                ),
            }
        else:
            missing = (
                "received_units"
                if not intake or not revision
                else ("damaged_units" if not inspection or not rule_seen else "required_units")
            )
            target = policies.get(revision) if missing == "required_units" and revision else None
            target = (
                target or sources.get(missing) or self._extract_document_search_result(messages)
            )
            name = "read_document" if target else "search_documents"
            arguments = (
                {"document_id": target}
                if target
                else {"query": self._extract_document_query(messages), "top_k": 3}
            )
        return ModelResponse(
            action=ToolCall(
                call_id=f"call_rule_{self._call_count}", name=name, arguments=arguments
            ),
            token_usage=usage,
            estimated_cost=cost,
        )

    def _chain_response(
        self, messages: list[Message], usage: TokenUsage, cost: EstimatedCost
    ) -> ModelResponse:
        """Follow public document references; retain only evidence visible in the request."""
        document = self._extract_document_result(messages)
        if document is None:
            first = self._extract_document_search_result(messages)
            name = "read_document" if first else "search_documents"
            arguments: dict[str, Any] = (
                {"document_id": first}
                if first
                else {"query": self._extract_document_query(messages), "top_k": 3}
            )
        else:
            link = re.search(r"Next document:\s*([A-Za-z0-9_-]+)", document["content"])
            if link or self.scenario in {"max_steps", "looping"}:
                name = "read_document"
                arguments = {"document_id": link.group(1) if link else "missing-document"}
            else:
                status = re.search(r"Status:\s*([A-Za-z0-9_-]+)", document["content"])
                if status is None:
                    raise ValueError("Document chain has neither a reference nor a status")
                evidence: set[str] = set()
                for message in messages:
                    if message.role == "tool" and isinstance(message.content, dict):
                        result = message.content.get("result")
                        read = result.get("document") if isinstance(result, dict) else None
                        if isinstance(read, dict):
                            identifier = read.get("evidence_id")
                            if isinstance(identifier, str):
                                evidence.add(identifier)
                name = "submit_answer"
                arguments = {
                    "answer": "wrong" if self.scenario == "wrong_answer" else status.group(1),
                    "evidence": sorted(evidence),
                }
        return ModelResponse(
            action=ToolCall(
                call_id=f"call_chain_{self._call_count}", name=name, arguments=arguments
            ),
            token_usage=usage,
            estimated_cost=cost,
        )

    def _document_response(
        self,
        messages: list[Message],
        token_usage: TokenUsage,
        estimated_cost: EstimatedCost,
    ) -> ModelResponse:
        """Complete a document search, read, and evidence submission chain."""
        search_result = self._extract_document_search_result(messages)
        document_result = self._extract_document_result(messages)
        if search_result is None:
            query = self._extract_document_query(messages)
            action = ToolCall(
                call_id=f"call_search_{self._call_count}",
                name="search_documents",
                arguments={"query": query, "top_k": 3},
            )
        elif document_result is None:
            action = ToolCall(
                call_id=f"call_read_{self._call_count}",
                name="read_document",
                arguments={"document_id": search_result},
            )
        else:
            content = document_result["content"]
            answer_match = re.search(
                r"(?:status|answer)\s*:\s*([a-zA-Z0-9_-]+)", content, flags=re.IGNORECASE
            )
            answer = answer_match.group(1) if answer_match else content.strip()
            action = ToolCall(
                call_id=f"call_submit_{self._call_count}",
                name="submit_answer",
                arguments={
                    "answer": answer,
                    "evidence": [document_result["evidence_id"]],
                },
            )
        return ModelResponse(
            action=action,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

    def _extract_target_order_id(self, messages: list[Message]) -> str:
        """Parse target order ID from public messages."""
        for msg in messages:
            if isinstance(msg.content, dict):
                target = msg.content.get("target_order_id")
                if isinstance(target, str):
                    return target
        raise ValueError("Public observation has no target order ID")

    def _extract_document_query(self, messages: list[Message]) -> str:
        """Read the public document search hint."""
        for msg in messages:
            if isinstance(msg.content, dict):
                query = msg.content.get("document_query")
                if isinstance(query, str) and query.strip():
                    return query
        return "status"

    def _extract_query_result(self, messages: list[Message]) -> dict[str, Any] | None:
        """Extract order query result from tool response messages."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                result = msg.content.get("result")
                if isinstance(result, dict) and "records" in result:
                    records = result.get("records")
                    if isinstance(records, list) and records:
                        record = records[0]
                        if isinstance(record, dict):
                            status = record.get("status")
                            evidence_id = record.get("evidence_id")
                            if isinstance(status, str) and isinstance(evidence_id, str):
                                return {"status": status, "evidence": [evidence_id]}
        return None

    def _extract_document_search_result(self, messages: list[Message]) -> str | None:
        """Return the first document ID from a successful search response."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                result = msg.content.get("result")
                if isinstance(result, dict):
                    documents = result.get("documents")
                    if isinstance(documents, list) and documents:
                        first = documents[0]
                        if isinstance(first, dict):
                            document_id = first.get("document_id")
                            if isinstance(document_id, str):
                                return document_id
        return None

    def _extract_document_result(self, messages: list[Message]) -> dict[str, str] | None:
        """Return document content and evidence from a successful read."""
        for msg in reversed(messages):
            if msg.role == "tool" and isinstance(msg.content, dict):
                result = msg.content.get("result")
                if isinstance(result, dict):
                    document = result.get("document")
                    if isinstance(document, dict):
                        content = document.get("content")
                        evidence_id = document.get("evidence_id")
                        if isinstance(content, str) and isinstance(evidence_id, str):
                            return {"content": content, "evidence_id": evidence_id}
        return None
