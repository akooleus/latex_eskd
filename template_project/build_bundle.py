#!/usr/bin/env python3
"""Build configured ESKD LaTeX documents and merge them into one bundle.

Project composition is described in ``project_manifest.toml``.
Supported document kinds:
- ``text_doc``: A4 portrait textual document; the title page may be excluded
  from the common sheet count via ``front_pages_excluded``.
- ``drawing_doc``: graphical sheet (for example A3 landscape).
- ``bom_doc``: separate bill of materials document; must stay A4 portrait.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "project_manifest.toml"


@dataclass(frozen=True)
class DocumentSpec:
    """A buildable document declared in ``project_manifest.toml``."""

    name: str
    kind: str
    source: Path
    sheet_meta: Path
    passes: int
    count_in_total: bool
    front_pages_excluded: int
    paper: str
    orientation: str
    stamp_mode: str
    items_json: Path | None = None
    generated_tex: Path | None = None

    @property
    def workdir(self) -> Path:
        return self.source.parent

    @property
    def pdf_path(self) -> Path:
        return self.source.with_suffix(".pdf")


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found in PATH")


def tail_output(stdout: str, stderr: str, max_lines: int = 60) -> str:
    lines = (stdout + "\n" + stderr).strip().splitlines()
    if not lines:
        return "no compiler output"
    return "\n".join(lines[-max_lines:])


def tex_env() -> dict[str, str]:
    """Expose template root to TeX so shared ESKD style files stay discoverable."""

    env = os.environ.copy()
    texinputs = env.get("TEXINPUTS", "")
    env["TEXINPUTS"] = (
        f"{ROOT}{os.pathsep}{texinputs}"
        if texinputs
        else f"{ROOT}{os.pathsep}"
    )
    return env


def run_checked(cmd: list[str], *, cwd: Path) -> None:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=tex_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{tail_output(result.stdout, result.stderr)}"
        )


def compile_latex(doc: DocumentSpec) -> None:
    for _ in range(doc.passes):
        run_checked(["xelatex", "-interaction=nonstopmode", doc.source.name], cwd=doc.workdir)


def pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not count pages for {pdf_path.name}\n{tail_output(result.stdout, result.stderr)}"
        )
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Pages field not found in pdfinfo output for {pdf_path.name}")
    return int(match.group(1))


def write_sheet_meta(path: Path, *, start_page: int, total_pages: int) -> None:
    path.write_text(
        "\n".join([
            f"\\setcounter{{page}}{{{start_page}}}",
            "\\makeatletter",
            f"\\@namedef{{r@LastPage}}{{{{}}{{{total_pages}}}}}",
            "\\global\\ESKD@enable@column@viitrue",
            "\\ESKDforceFirstStampPage",
            "\\makeatother",
            "",
        ]),
        encoding="utf-8",
    )


def merge_pdfs(pdf_paths: list[Path], output_path: Path) -> None:
    if not pdf_paths:
        raise RuntimeError("No PDFs to merge")
    if len(pdf_paths) == 1:
        shutil.copyfile(pdf_paths[0], output_path)
        return
    run_checked(["pdfunite", *(str(p) for p in pdf_paths), str(output_path)], cwd=ROOT)


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def designator_sort_key(designator: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"([A-Za-zА-Яа-я]+)(\d+)", designator)
    if not match:
        return (designator, 0, designator)
    prefix, number = match.groups()
    return (prefix, int(number), designator)


def format_designator_list(designators: list[str]) -> str:
    parsed: list[tuple[str, int, str]] = []
    raw: list[str] = []
    for designator in designators:
        match = re.fullmatch(r"([A-Za-zА-Яа-я]+)(\d+)", designator)
        if not match:
            raw.append(designator)
            continue
        prefix, number = match.groups()
        parsed.append((prefix, int(number), designator))

    if not parsed:
        return ", ".join(raw)

    parsed.sort(key=lambda item: (item[0], item[1]))
    chunks: list[str] = []
    i = 0
    while i < len(parsed):
        prefix, _, _ = parsed[i]
        j = i
        while (
            j + 1 < len(parsed)
            and parsed[j + 1][0] == prefix
            and parsed[j + 1][1] == parsed[j][1] + 1
        ):
            j += 1
        run = parsed[i : j + 1]
        if len(run) >= 3:
            chunks.append(f"{prefix}{run[0][1]}...{prefix}{run[-1][1]}")
        else:
            chunks.extend(item[2] for item in run)
        i = j + 1

    chunks.extend(raw)
    return ", ".join(chunks)


def wrap_designator_text(text: str, max_line_len: int = 20) -> list[str]:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        return [text]

    lines: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else f"{current}, {part}"
        if current and len(candidate) > max_line_len:
            lines.append(current)
            current = part
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def load_bom_json(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    groups = data.get("groups", [])
    if not isinstance(groups, list):
        raise RuntimeError("items.json: 'groups' must be a list")
    return groups


def build_group_rows(
    title: str,
    items: list[dict[str, object]],
    *,
    insert_blank_before: bool,
) -> list[tuple[str, list[dict[str, str | bool]]]]:
    blocks: list[tuple[str, list[dict[str, str | bool]]]] = []
    header_rows: list[dict[str, str | bool]] = []
    if insert_blank_before:
        header_rows.append({
            "kind": "blank",
            "pos": "",
            "name": "",
            "qty": "",
            "note": "",
            "line_after": True,
        })
    header_rows.append({
        "kind": "group",
        "pos": "",
        "name": latex_escape(title),
        "qty": "",
        "note": "",
        "line_after": True,
    })
    blocks.append(("section_header", header_rows))

    for item in items:
        raw_designators = item.get("designators", [])
        if isinstance(raw_designators, str):
            designators = [raw_designators]
        elif isinstance(raw_designators, list):
            designators = [str(x) for x in raw_designators]
        else:
            raise RuntimeError("items.json: item.designators must be string or list")

        ordered = sorted(designators, key=designator_sort_key)
        designator_lines = wrap_designator_text(format_designator_list(ordered))
        name = latex_escape(str(item.get("name", "")))
        note = latex_escape(str(item.get("note", "")))
        qty = str(item.get("qty", len(designators) if designators else ""))

        item_rows: list[dict[str, str | bool]] = [{
            "kind": "item",
            "pos": latex_escape(designator_lines[0] if designator_lines else ""),
            "name": name,
            "qty": qty,
            "note": note,
            "line_after": len(designator_lines) <= 1,
        }]
        for continuation in designator_lines[1:]:
            item_rows.append({
                "kind": "item",
                "pos": latex_escape(continuation),
                "name": "",
                "qty": "",
                "note": "",
                "line_after": False,
            })
        item_rows[-1]["line_after"] = True
        blocks.append(("item", item_rows))

    return blocks


def render_bom_page(rows: list[dict[str, str | bool]], *, is_first_page: bool) -> str:
    preview_px_to_mm = 25.4 / 150.0
    origin_x_mm = 20.0 - 16.0 * preview_px_to_mm
    origin_y_mm = 5.0 + 7.0 * preview_px_to_mm
    top_y = 287
    header_h = 15
    row_h = 8
    bottom_y = 40 if is_first_page else 15
    header_bottom_y = top_y - header_h

    draw: list[str] = [
        "\\begin{tikzpicture}[remember picture,overlay]\n",
        (
            "\\node[anchor=north west,inner sep=0pt,outer sep=0pt] "
            f"at ([xshift={origin_x_mm:.3f}mm,yshift=-{origin_y_mm:.3f}mm]current page.north west) {{%\n"
        ),
        "\\setlength{\\unitlength}{1mm}%\n",
        "\\begin{picture}(185,287)(0,0)\n",
        "\\linethickness{\\ESKDlineThin}\n",
        f"\\put(20,{bottom_y}){{\\line(0,1){{{top_y - bottom_y}}}}}\n",
        f"\\put(130,{bottom_y}){{\\line(0,1){{{top_y - bottom_y}}}}}\n",
        f"\\put(140,{bottom_y}){{\\line(0,1){{{top_y - bottom_y}}}}}\n",
        "\\linethickness{\\ESKDlineThick}\n",
        f"\\put(0,{header_bottom_y}){{\\line(1,0){{185}}}}\n",
        "\\linethickness{\\ESKDlineThin}\n",
        "\\AmpBOMCell{0}{272}{20mm}{15mm}{\\centering\\AmpBOMHeadFont Поз.\\\\обозначение}\n",
        "\\AmpBOMCell{20}{272}{110mm}{15mm}{\\centering\\AmpBOMHeadFont Наименование}\n",
        "\\AmpBOMCell{130}{272}{10mm}{15mm}{\\centering\\AmpBOMHeadFont Кол.}\n",
        "\\AmpBOMCell{140}{272}{45mm}{15mm}{\\centering\\AmpBOMHeadFont Примечание}\n",
    ]

    for idx, row in enumerate(rows):
        row_bottom = header_bottom_y - (idx + 1) * row_h
        row_kind = str(row["kind"])
        pos = str(row["pos"])
        name = str(row["name"])
        qty = str(row["qty"])
        note = str(row["note"])

        if row_kind == "group":
            draw.append(
                f"\\AmpBOMCell{{20}}{{{row_bottom}}}{{110mm}}{{8mm}}{{\\centering\\AmpBOMFont\\underline{{{name}}}}}\n"
            )
        else:
            draw.append(
                f"\\AmpBOMCell{{0}}{{{row_bottom}}}{{20mm}}{{8mm}}{{\\centering\\AmpBOMPosFont {pos}}}\n"
            )
            draw.append(
                f"\\AmpBOMCell{{20}}{{{row_bottom}}}{{110mm}}{{8mm}}{{\\AmpBOMFont\\hspace*{{1.5mm}}{name}}}\n"
            )
            draw.append(
                f"\\AmpBOMCell{{130}}{{{row_bottom}}}{{10mm}}{{8mm}}{{\\centering\\AmpBOMFont {qty}}}\n"
            )
            draw.append(
                f"\\AmpBOMCell{{140}}{{{row_bottom}}}{{45mm}}{{8mm}}{{\\AmpBOMFont\\hspace*{{1.5mm}}{note}}}\n"
            )

        if idx < len(rows) - 1 and bool(row["line_after"]):
            draw.append(f"\\put(0,{row_bottom}){{\\line(1,0){{185}}}}\n")

    draw.append("\\end{picture}};\n")
    draw.append("\\end{tikzpicture}\n")
    draw.append("\\null\n")
    return "".join(draw)


def generate_bom_tex(doc: DocumentSpec) -> None:
    if doc.items_json is None or doc.generated_tex is None:
        raise RuntimeError("BOM document requires items_json and generated_tex paths")

    groups = load_bom_json(doc.items_json)

    blocks: list[tuple[str, list[dict[str, str | bool]]]] = []
    for group in groups:
        title = str(group.get("title", ""))
        items = group.get("items", [])
        if not isinstance(items, list):
            raise RuntimeError("items.json: group.items must be a list")
        blocks.extend(build_group_rows(title, items, insert_blank_before=bool(blocks)))

    pages: list[list[dict[str, str | bool]]] = []
    current_page: list[dict[str, str | bool]] = []
    page_capacity = 29
    idx = 0
    while idx < len(blocks):
        block_type, block_rows = blocks[idx]
        remaining = page_capacity - len(current_page)
        needed = len(block_rows)
        if block_type == "section_header" and idx + 1 < len(blocks):
            needed += len(blocks[idx + 1][1])
        if current_page and needed > remaining:
            while len(current_page) < page_capacity:
                current_page.append({
                    "kind": "blank",
                    "pos": "",
                    "name": "",
                    "qty": "",
                    "note": "",
                    "line_after": True,
                })
            pages.append(current_page)
            current_page = []
            page_capacity = 32
            continue
        if len(block_rows) > remaining:
            while len(current_page) < page_capacity:
                current_page.append({
                    "kind": "blank",
                    "pos": "",
                    "name": "",
                    "qty": "",
                    "note": "",
                    "line_after": True,
                })
            pages.append(current_page)
            current_page = []
            page_capacity = 32
            continue
        current_page.extend(block_rows)
        idx += 1

    while len(current_page) < page_capacity:
        current_page.append({
            "kind": "blank",
            "pos": "",
            "name": "",
            "qty": "",
            "note": "",
            "line_after": True,
        })
    pages.append(current_page)

    parts: list[str] = []
    for page_index, page_rows in enumerate(pages):
        parts.append(render_bom_page(page_rows, is_first_page=page_index == 0))
        if page_index < len(pages) - 1:
            parts.append("\\newpage\n")

    doc.generated_tex.write_text("".join(parts), encoding="utf-8")


def manifest_value(cfg: dict[str, object], key: str) -> object:
    if key not in cfg:
        raise RuntimeError(f"Manifest entry is missing '{key}'")
    return cfg[key]


def load_manifest() -> list[DocumentSpec]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError(f"Manifest not found: {MANIFEST_PATH}")

    with MANIFEST_PATH.open("rb") as file:
        data = tomllib.load(file)

    bundle_cfg = data.get("bundle")
    documents_cfg = data.get("documents")
    if not isinstance(bundle_cfg, dict) or not isinstance(documents_cfg, dict):
        raise RuntimeError("Manifest must contain [bundle] and [documents] sections")

    order = bundle_cfg.get("order")
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise RuntimeError("[bundle].order must be a list of document names")

    docs: list[DocumentSpec] = []
    for name in order:
        cfg = documents_cfg.get(name)
        if not isinstance(cfg, dict):
            raise RuntimeError(f"Document '{name}' is missing in [documents]")

        kind = str(manifest_value(cfg, "kind"))
        source = ROOT / str(manifest_value(cfg, "source"))
        sheet_meta = ROOT / str(manifest_value(cfg, "sheet_meta"))
        passes = int(manifest_value(cfg, "passes"))
        count_in_total = bool(manifest_value(cfg, "count_in_total"))
        front_pages_excluded = int(cfg.get("front_pages_excluded", 0))
        paper = str(manifest_value(cfg, "paper")).lower()
        orientation = str(manifest_value(cfg, "orientation")).lower()
        stamp_mode = str(manifest_value(cfg, "stamp_mode")).lower()

        spec = DocumentSpec(
            name=name,
            kind=kind,
            source=source,
            sheet_meta=sheet_meta,
            passes=passes,
            count_in_total=count_in_total,
            front_pages_excluded=front_pages_excluded,
            paper=paper,
            orientation=orientation,
            stamp_mode=stamp_mode,
            items_json=(ROOT / str(cfg["items_json"])) if "items_json" in cfg else None,
            generated_tex=(ROOT / str(cfg["generated_tex"])) if "generated_tex" in cfg else None,
        )
        validate_document_spec(spec)
        docs.append(spec)

    return docs


def validate_document_spec(doc: DocumentSpec) -> None:
    if doc.kind not in {"text_doc", "drawing_doc", "bom_doc"}:
        raise RuntimeError(f"Unsupported document kind: {doc.kind}")
    if not doc.source.exists():
        raise RuntimeError(f"Source TeX not found for '{doc.name}': {doc.source}")
    if doc.passes < 1:
        raise RuntimeError(f"Document '{doc.name}' must have at least one LaTeX pass")
    if doc.front_pages_excluded < 0:
        raise RuntimeError(f"Document '{doc.name}' has negative front_pages_excluded")
    if doc.stamp_mode not in {"none", "first", "first_large_then_small"}:
        raise RuntimeError(f"Unsupported stamp_mode for '{doc.name}': {doc.stamp_mode}")

    if doc.kind == "text_doc":
        if doc.paper != "a4" or doc.orientation != "portrait":
            raise RuntimeError("text_doc must stay A4 portrait")
    if doc.kind == "bom_doc":
        if doc.paper != "a4" or doc.orientation != "portrait":
            raise RuntimeError("bom_doc must stay A4 portrait")
        if doc.items_json is None or doc.generated_tex is None:
            raise RuntimeError("bom_doc requires items_json and generated_tex paths")


def build_bundle() -> None:
    require_tool("xelatex")
    require_tool("pdfinfo")
    require_tool("pdfunite")

    docs = load_manifest()

    for doc in docs:
        if doc.kind == "bom_doc":
            generate_bom_tex(doc)

    for doc in docs:
        doc.sheet_meta.write_text("", encoding="utf-8")

    for doc in docs:
        compile_latex(doc)

    page_counts = {doc.name: pdf_page_count(doc.pdf_path) for doc in docs}
    sheet_counts = {
        doc.name: max(page_counts[doc.name] - doc.front_pages_excluded, 0)
        if doc.count_in_total
        else 0
        for doc in docs
    }

    total_pages = sum(sheet_counts.values())
    start_page = 1
    for doc in docs:
        write_sheet_meta(doc.sheet_meta, start_page=start_page, total_pages=total_pages)
        if doc.count_in_total:
            start_page += sheet_counts[doc.name]

    for doc in docs:
        compile_latex(doc)

    merge_pdfs([doc.pdf_path for doc in docs], ROOT / "bundle.pdf")


def main() -> int:
    try:
        build_bundle()
    except Exception as exc:  # noqa: BLE001
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print("bundle created:", ROOT / "bundle.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
