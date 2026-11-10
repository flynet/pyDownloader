"""Собирает строковые литералы с кириллицей по модулям (для каталога переводов).

Запуск: ``uv run python tools/list_strings.py``. Вывод — группы по файлам,
литералы идут в том порядке, в котором они встречаются в исходнике.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path("src") / "pydownloader"
CYRILLIC = "\u0400-\u04ff"


def literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text("utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if any("\u0400" <= ch <= "\u04ff" for ch in value):
                out.append(value)
    # docstrings are developer text, not interface text
    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        text = leading_docstring(node)
        if text is not None:
            docstrings.add(text)
    return [value for value in out if value not in docstrings]


def leading_docstring(node: ast.Module | ast.ClassDef | ast.FunctionDef) -> str | None:
    """The first statement of ``node`` when it is a docstring, else None."""
    body = node.body
    if not body:
        return None
    expr = body[0]
    if isinstance(expr, ast.Expr) and isinstance(expr.value, ast.Constant):
        value = expr.value.value
        return value if isinstance(value, str) else None
    return None


def main() -> int:
    lines: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        values = literals(path)
        if not values:
            continue
        lines.append(f"### {path.as_posix()} ({len(values)})")
        lines.extend(f"- {value!r}" for value in values)
        lines.append("")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("strings.txt")
    out.write_text("\n".join(lines), "utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
