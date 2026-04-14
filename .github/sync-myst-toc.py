#!/usr/bin/env python3
"""
Sync myst.yml TOC with notebooks on disk.

Each curriculum module is a top-level folder (e.g. fundamentals/) containing:
  lecture_notebooks/, labs/*, homeworks/HW*

Add new modules by extending MODULES below.
"""
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
MYST_PATH = REPO_ROOT / "myst.yml"

EXIT_SUCCESS = 0
EXIT_ERROR = 2

# (folder_name_under_repo, sidebar_title). Only folders that exist are scanned.
MODULES: list[tuple[str, str]] = [
    ("fundamentals", "Fundamentals"),
    ("visualizations", "Visualizations"),
]
EXTERNAL_LINKS: list[dict[str, str]] = [
    {"title": "About the Curriculum", "url": "https://dubois-ctds.github.io/curriculum/"},
]

LAB_DIR_RE = re.compile(r"^lab(\d+)$", re.IGNORECASE)
HW_DIR_RE = re.compile(r"^hw(\d+)$", re.IGNORECASE)


def natural_sort_key(s: str) -> tuple:
    parts = re.split(r"(\d+)", s)
    key: list = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p)))
        else:
            key.append((1, p.lower()))
    return tuple(key)


def humanize_stem(stem: str) -> str:
    return stem.replace("_", " ")


def find_numbered_notebooks(parent_dir: str, prefix: str, title_fmt: str) -> list[dict]:
    """Find all prefixNN/prefixNN.ipynb under parent_dir, sorted by NN."""
    base = REPO_ROOT / parent_dir
    if not base.is_dir():
        return []
    pattern = re.compile(rf"^{prefix}(\d+)$")
    entries = []
    for path in sorted(base.iterdir()):
        if not path.is_dir():
            continue
        m = pattern.match(path.name)
        if not m:
            continue
        num = m.group(1)
        nb = path / f"{path.name}.ipynb"
        if nb.is_file():
            rel = str(nb.relative_to(REPO_ROOT))
            title = title_fmt.format(num=int(num), znum=num.zfill(2))
            entries.append({"title": title, "file": rel})
    entries.sort(key=lambda e: int(re.search(r"\d+", e["file"]).group()))
    return entries


def find_module_lecture_notebooks(module_root: Path) -> list[dict]:
    base = module_root / "lecture_notebooks"
    if not base.is_dir():
        return []
    paths = sorted(base.glob("*.ipynb"), key=lambda p: natural_sort_key(p.name))
    entries = []
    for nb in paths:
        rel = str(nb.relative_to(REPO_ROOT))
        entries.append({"title": humanize_stem(nb.stem), "file": rel})
    return entries


def find_module_labs(module_root: Path) -> list[dict]:
    base = module_root / "labs"
    if not base.is_dir():
        return []
    dirs = [p for p in base.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: natural_sort_key(p.name))
    entries: list[dict] = []
    for d in dirs:
        notebooks = sorted(d.glob("*.ipynb"), key=lambda p: natural_sort_key(p.name))
        if not notebooks:
            continue
        m = LAB_DIR_RE.match(d.name)
        lab_label = f"Lab {m.group(1).zfill(2)}" if m else d.name
        if len(notebooks) == 1:
            nb = notebooks[0]
            entries.append({"title": lab_label, "file": str(nb.relative_to(REPO_ROOT))})
        else:
            for nb in notebooks:
                entries.append(
                    {
                        "title": f"{lab_label} — {nb.stem}",
                        "file": str(nb.relative_to(REPO_ROOT)),
                    }
                )
    return entries


def find_module_homeworks(module_root: Path) -> list[dict]:
    base = module_root / "homeworks"
    if not base.is_dir():
        return []
    hw_dirs: list[tuple[int, Path]] = []
    for path in base.iterdir():
        if not path.is_dir():
            continue
        m = HW_DIR_RE.match(path.name)
        if not m:
            continue
        hw_dirs.append((int(m.group(1)), path))
    hw_dirs.sort(key=lambda t: t[0])
    entries: list[dict] = []
    for num, d in hw_dirs:
        znum = str(num).zfill(2)
        label = f"Homework {znum}"
        notebooks = sorted(d.rglob("*.ipynb"), key=lambda p: natural_sort_key(str(p.relative_to(d))))
        if not notebooks:
            continue
        if len(notebooks) == 1:
            nb = notebooks[0]
            entries.append({"title": label, "file": str(nb.relative_to(REPO_ROOT))})
        else:
            for nb in notebooks:
                entries.append(
                    {
                        "title": f"{label} — {nb.stem}",
                        "file": str(nb.relative_to(REPO_ROOT)),
                    }
                )
    return entries


def build_module_toc_part(folder_name: str, sidebar_title: str) -> Optional[dict]:
    """One top-level part (e.g. Fundamentals) with nested lecture/lab/homework sections."""
    root = REPO_ROOT / folder_name
    if not root.is_dir():
        return None

    children: list[dict] = []
    lectures = find_module_lecture_notebooks(root)
    if lectures:
        children.append({"title": "Lecture notebooks", "children": lectures})

    labs = find_module_labs(root)
    if labs:
        children.append({"title": "Labs", "children": labs})

    homework = find_module_homeworks(root)
    if homework:
        children.append({"title": "Homework", "children": homework})

    if not children:
        return None
    return {"title": sidebar_title, "children": children}


def main() -> int:
    if not MYST_PATH.is_file():
        print(f"Error: {MYST_PATH} not found", file=sys.stderr)
        return EXIT_ERROR

    toc: list[dict] = []

    intro = REPO_ROOT / "intro.md"
    if intro.exists():
        toc.append({"file": "intro.md"})

    for folder_name, sidebar_title in MODULES:
        part = build_module_toc_part(folder_name, sidebar_title)
        if part is not None:
            toc.append(part)

    lectures = find_numbered_notebooks("lec", "lec", "Lecture {znum}")
    if lectures:
        toc.append({"title": "Lectures", "children": lectures})

    labs = find_numbered_notebooks("lab", "lab", "Lab {znum}")
    if labs:
        toc.append({"title": "Labs (legacy)", "children": labs})

    homework = find_numbered_notebooks("hw", "hw", "Homework {znum}")
    if homework:
        toc.append({"title": "Homework (legacy)", "children": homework})

    projects = find_numbered_notebooks("project", "project", "Project {znum}")
    if projects:
        toc.append({"title": "Projects", "children": projects})

    sandbox_nb = REPO_ROOT / "sandbox" / "sandbox.ipynb"
    if sandbox_nb.exists():
        toc.append(
            {
                "title": "Sandbox",
                "children": [{"title": "Sandbox", "file": "sandbox/sandbox.ipynb"}],
            }
        )

    for external_link in EXTERNAL_LINKS:
        toc.append(external_link)

    try:
        with open(MYST_PATH, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error: invalid YAML in {MYST_PATH}: {e}", file=sys.stderr)
        return EXIT_ERROR

    if data is None:
        data = {}
    if "project" not in data:
        data["project"] = {}

    old_toc = data["project"].get("toc", [])
    if old_toc == toc:
        return EXIT_SUCCESS

    data["project"]["toc"] = toc
    with open(MYST_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return EXIT_SUCCESS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
