"""
Generates POWERBI_MEASURES.md directly from MEASURE_DOCS in semantic_layer.py.

This file is generated, not hand-written, on purpose: MEASURE_DOCS is the one
place SQL, DAX, and plain-language descriptions for a measure are defined
together. Hand-copying DAX into a separate markdown file would create a
second copy that silently drifts the moment someone updates a measure in
code and forgets the doc. Re-run this after any change to MEASURE_DOCS:
    python3 warehouse/generate_powerbi_measures_doc.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from warehouse.semantic_layer import MEASURE_DOCS

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "POWERBI_MEASURES.md")

HEADER = """# Power BI Measures (generated)

**Do not hand-edit this file.** It is generated from `warehouse/semantic_layer.py::MEASURE_DOCS` by
`warehouse/generate_powerbi_measures_doc.py`, which is the single source of truth for what each
measure means, in both SQL (used by this prototype's DuckDB backend) and DAX (for Power BI).

For each measure below: paste the DAX into Power BI Desktop's "New Measure" on the appropriate
table (named in the SQL view's underlying table), after importing the tables per
POWERBI_MIGRATION.md.

---
"""


def main():
    lines = [HEADER]
    for view_name, doc in MEASURE_DOCS.items():
        lines.append(f"## {doc['label']}\n")
        lines.append(f"*Source view (this prototype): `{view_name}`*\n")
        lines.append(f"**Definition:** {doc['description']}\n")
        lines.append("**DAX for Power BI:**\n")
        lines.append(f"```dax\n{doc['dax']}\n```\n")
        if doc.get("power_query_notes"):
            lines.append(f"**Modeling notes:** {doc['power_query_notes']}\n")
        lines.append("---\n")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
