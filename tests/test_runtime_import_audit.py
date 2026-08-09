"""Packaged runtime import-boundary audit tests."""

from __future__ import annotations

from scripts.audit_runtime_imports import audit_runtime_imports


def test_runtime_import_graph_has_only_approved_third_party_dependencies() -> None:
    report = audit_runtime_imports()
    assert report["passed"] is True
    assert report["third_party_runtime_dependencies"] == ["PIL", "PySide6"]
    assert report["forbidden_found"] == []
    assert report["unexpected_third_party"] == []
    assert report["suspicious_absolute_paths"] == []
