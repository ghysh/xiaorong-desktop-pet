"""Static import-boundary audit for the packaged desktop_pet source tree."""

from __future__ import annotations

import ast
import json
import re
import sys

from desktop_pet.paths import PROJECT_ROOT

SOURCE_ROOT = PROJECT_ROOT / "src" / "desktop_pet"
REPORT_PATH = PROJECT_ROOT / "build" / "reports" / "runtime_import_audit_1_1_0.json"
ALLOWED_THIRD_PARTY = {"PIL", "PySide6"}
FORBIDDEN = {"PyInstaller", "cv2", "httpx", "matplotlib", "numpy", "pytest", "requests", "ruff"}
ABSOLUTE_PATH_PATTERN = re.compile(r"(?i)(?:[a-z]:[\\/]|D:\\DesktopPet)")


def audit_runtime_imports() -> dict[str, object]:
    project_modules: set[str] = set()
    standard_library: set[str] = set()
    third_party: set[str] = set()
    dynamic_imports: list[dict[str, object]] = []
    suspicious_paths: list[dict[str, object]] = []
    module_records: list[dict[str, object]] = []

    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Call):
                function_name = _call_name(node.func)
                if function_name in {"__import__", "importlib.import_module"}:
                    dynamic_imports.append({"file": relative, "line": node.lineno, "call": function_name})
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if ABSOLUTE_PATH_PATTERN.search(node.value):
                    suspicious_paths.append({"file": relative, "line": node.lineno, "value": node.value})
        for imported in imports:
            root = imported.split(".", 1)[0]
            if root == "desktop_pet":
                project_modules.add(imported)
            elif root in sys.stdlib_module_names:
                standard_library.add(root)
            else:
                third_party.add(root)
        module_records.append({"file": relative, "imports": sorted(imports)})

    forbidden_found = sorted(third_party & FORBIDDEN)
    unexpected = sorted(third_party - ALLOWED_THIRD_PARTY)
    passed = not forbidden_found and not unexpected and not suspicious_paths
    return {
        "passed": passed,
        "source_root": "src/desktop_pet",
        "modules": module_records,
        "project_imports": sorted(project_modules),
        "standard_library": sorted(standard_library),
        "third_party_runtime_dependencies": sorted(third_party),
        "allowed_third_party": sorted(ALLOWED_THIRD_PARTY),
        "forbidden_dependencies": sorted(FORBIDDEN),
        "forbidden_found": forbidden_found,
        "unexpected_third_party": unexpected,
        "dynamic_imports": dynamic_imports,
        "suspicious_absolute_paths": suspicious_paths,
    }


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return ""


def main() -> int:
    report = audit_runtime_imports()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Runtime import audit: {'passed' if report['passed'] else 'failed'}")
    print(f"Report: {REPORT_PATH}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
