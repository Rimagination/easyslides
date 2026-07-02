"""Shared text capacity helpers for EasySlides template slots."""

from __future__ import annotations

from dataclasses import dataclass
import textwrap
from typing import Any


@dataclass(frozen=True)
class SlotCapacity:
    slot_id: str
    role: str
    font_size_px: float
    min_font_size_px: float
    line_height: float
    max_chars_per_line_zh: int
    max_lines: int
    capacity_chars: int
    overflow_action: str


@dataclass(frozen=True)
class FitResult:
    lines: list[str]
    raw_line_count: int
    input_chars: int
    rendered_chars: int
    input_over_capacity: bool
    output_overflow: bool
    action: str


def _role_defaults(layouts: dict[str, Any], role: str) -> dict[str, Any]:
    policy = layouts.get("text_fit_policy")
    if not isinstance(policy, dict):
        raise ValueError("layouts must define text_fit_policy")
    defaults = policy.get("role_defaults")
    if not isinstance(defaults, dict):
        raise ValueError("text_fit_policy must define role_defaults")
    role_default = defaults.get(role) or defaults.get("body")
    if not isinstance(role_default, dict):
        raise ValueError(f"role {role!r} has no capacity default")
    return role_default


def resolve_slot_capacity(layouts: dict[str, Any], slot: dict[str, Any]) -> SlotCapacity:
    """Resolve slot-specific capacity from slot_models plus role defaults."""
    slot_id = str(slot.get("slot_id") or "")
    role = str(slot.get("role") or "body")
    defaults = _role_defaults(layouts, role)
    max_lines = int(slot.get("max_lines") or defaults.get("max_lines") or 1)
    chars = int(defaults["max_chars_per_line_zh"])
    return SlotCapacity(
        slot_id=slot_id,
        role=role,
        font_size_px=float(defaults["default_font_size_px"]),
        min_font_size_px=float(defaults["min_font_size_px"]),
        line_height=float(defaults["line_height"]),
        max_chars_per_line_zh=chars,
        max_lines=max_lines,
        capacity_chars=max_lines * chars,
        overflow_action=str(defaults["overflow_action"]),
    )


def wrap_text_to_capacity(text: str, capacity: SlotCapacity) -> tuple[list[str], int]:
    """Wrap text to a slot width and return rendered lines plus raw line count."""
    width = max(int(capacity.max_chars_per_line_zh), 1)
    max_lines = max(int(capacity.max_lines), 1)
    lines = textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False)
    if not lines and text == "":
        lines = [""]
    return lines[:max_lines], len(lines)


def fit_text_to_capacity(text: str, capacity: SlotCapacity) -> FitResult:
    """Fit text into a capacity contract without allowing rendered overflow."""
    lines, raw_line_count = wrap_text_to_capacity(text, capacity)
    rendered_chars = sum(len(line) for line in lines)
    input_over_capacity = len(text) > capacity.capacity_chars or raw_line_count > capacity.max_lines
    output_overflow = (
        len(lines) > capacity.max_lines
        or any(len(line) > capacity.max_chars_per_line_zh for line in lines)
    )
    return FitResult(
        lines=lines,
        raw_line_count=raw_line_count,
        input_chars=len(text),
        rendered_chars=rendered_chars,
        input_over_capacity=input_over_capacity,
        output_overflow=output_overflow,
        action="compressed_or_split_before_render" if input_over_capacity else "within_capacity",
    )
