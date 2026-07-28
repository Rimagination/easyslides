#!/usr/bin/env python3
"""Shared renderer metadata and dispatch registry for component packages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


SCHEMA_VERSION = "easyslides.component_renderer_registry.v1"
SVG_TARGET = "svg"
PPTX_TARGET = "native_pptx"
RendererHandler = Callable[..., Any]


@dataclass(frozen=True)
class RendererSpec:
    renderer_id: str
    display_name: str
    supported_targets: tuple[str, ...]
    payload_contract: str = "component_story_payload"


class RendererRegistryError(ValueError):
    """Raised when a component refers to an unavailable renderer contract."""


class ComponentRendererRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, RendererSpec] = {}
        self._handlers: dict[tuple[str, str], RendererHandler] = {}

    def register_spec(self, spec: RendererSpec) -> None:
        existing = self._specs.get(spec.renderer_id)
        if existing and existing != spec:
            raise RendererRegistryError(f"renderer_id {spec.renderer_id!r} is already registered with a different spec")
        self._specs[spec.renderer_id] = spec

    def register_handler(self, renderer_id: str, target: str, handler: RendererHandler) -> None:
        spec = self._specs.get(renderer_id)
        if spec is None:
            raise RendererRegistryError(f"renderer_id {renderer_id!r} has no registered spec")
        if target not in spec.supported_targets:
            raise RendererRegistryError(f"renderer {renderer_id!r} does not support target {target!r}")
        self._handlers[(renderer_id, target)] = handler

    def has_spec(self, renderer_id: str) -> bool:
        return renderer_id in self._specs

    def spec(self, renderer_id: str) -> RendererSpec:
        try:
            return self._specs[renderer_id]
        except KeyError as exc:
            raise RendererRegistryError(f"unknown renderer_id {renderer_id!r}") from exc

    def renderer_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def validate(self, renderer_id: str, *, target: str | None = None) -> dict[str, Any]:
        if not self.has_spec(renderer_id):
            return {
                "status": "fail",
                "renderer_id": renderer_id,
                "issues": [f"unknown renderer_id {renderer_id!r}"],
            }
        spec = self.spec(renderer_id)
        if target and target not in spec.supported_targets:
            return {
                "status": "fail",
                "renderer_id": renderer_id,
                "issues": [f"renderer does not support target {target!r}"],
            }
        return {
            "status": "pass",
            "renderer_id": renderer_id,
            "supported_targets": list(spec.supported_targets),
            "payload_contract": spec.payload_contract,
            "issues": [],
        }

    def render(self, target: str, renderer_id: str, *args: Any, **kwargs: Any) -> Any:
        self.validate(renderer_id, target=target)
        handler = self._handlers.get((renderer_id, target))
        if handler is None:
            raise RendererRegistryError(f"renderer {renderer_id!r} has no handler for target {target!r}")
        return handler(*args, **kwargs)


REGISTRY = ComponentRendererRegistry()

for _spec in (
    RendererSpec("three_card_summary", "Three Card Summary", (SVG_TARGET, PPTX_TARGET)),
    RendererSpec("process_timeline", "Process Timeline", (SVG_TARGET, PPTX_TARGET)),
    RendererSpec("figure_with_notes", "Figure With Notes", (SVG_TARGET, PPTX_TARGET)),
    RendererSpec("kpi_row_3", "KPI Row 3", (SVG_TARGET, PPTX_TARGET)),
    RendererSpec("comparison_pair", "Comparison Pair", (SVG_TARGET, PPTX_TARGET)),
    RendererSpec("evidence_stack", "Evidence Stack", (SVG_TARGET, PPTX_TARGET)),
    RendererSpec("source_template_projection", "Source Template Projection", (SVG_TARGET,)),
):
    REGISTRY.register_spec(_spec)


def resolve_renderer_id(component: dict[str, Any]) -> str:
    return str(component.get("renderer_id") or component.get("component_id") or "")


def supported_renderer_ids() -> tuple[str, ...]:
    return REGISTRY.renderer_ids()


def validate_renderer_id(renderer_id: str, *, target: str | None = None) -> dict[str, Any]:
    return REGISTRY.validate(renderer_id, target=target)


def register_renderer_handler(renderer_id: str, target: str, handler: RendererHandler) -> None:
    REGISTRY.register_handler(renderer_id, target, handler)


def render_registered(target: str, renderer_id: str, *args: Any, **kwargs: Any) -> Any:
    return REGISTRY.render(target, renderer_id, *args, **kwargs)
