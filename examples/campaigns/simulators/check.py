"""Check sealed tutorial outputs and compare C1 work across CPU layouts."""

import json
from pathlib import Path


def signature(summary):
    """Everything that must not depend on the CPU layout."""
    return [
        (
            a["model"],
            a.get("fast"),
            a["route"],
            a["seed"],
            a["actual_evaluations"],
            a["search_work"],
            a["validation_work"],
            a["rates"],
            a["training_loss"],
            a["holdout_loss"],
        )
        for a in summary["arms"]
    ]


def layout_signatures(name, record):
    rows = []
    for run in record["runs"]:
        summary = run.get("summary")
        if summary is None:
            raise ValueError(f"{name}: task {run.get('index')} has no summary")
        if summary["budgets"]["threads"] != record["inner"]:
            raise ValueError(
                f"{name}: task {run['index']} ran with "
                f"{summary['budgets']['threads']} threads, not {record['inner']}"
            )
        rows.append(signature(summary))
    return rows


def check(expected, rows):
    if sorted(rows) != sorted(expected):
        raise ValueError("missing or unexpected sealed summaries")
    failed = sorted(name for name, r in rows.items() if r.get("passed") is not True)
    if failed:
        raise ValueError("numerical tutorial checks failed: " + ", ".join(failed))
    layouts = sorted(
        (name, r) for name, r in rows.items() if name.startswith("layout-")
    )
    if not layouts:
        raise ValueError("no CPU-layout evidence")
    reference_name = layouts[0][0]
    reference = layout_signatures(*layouts[0])
    for name, record in layouts:
        if record["outer"] * record["inner"] > record["cpu_slots"]:
            raise ValueError("CPU allowance exceeded: " + name)
        if layout_signatures(name, record) != reference:
            raise ValueError(
                f"fixed work or numerical results differ between {name} and "
                f"{reference_name}"
            )
    return dict(
        passed=True,
        checked_summaries=len(rows),
        identical_C1_work_and_results=True,
        layouts=[
            dict(
                name=name,
                outer=r["outer"],
                inner=r["inner"],
                seconds=r["total_seconds"],
                tasks=r["tasks"],
            )
            for name, r in layouts
        ],
        interpretation="Descriptive wall times include Python startup and complete C1 validation. One smoke measurement is not a scaling result. CFD prescribed transport is serial and is reported separately.",
    )


def main():
    expected = json.loads(Path("expected.json").read_text())
    rows = {p.stem: json.loads(p.read_text()) for p in Path("results").glob("*.json")}
    report = check(expected, rows)
    Path("checks.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
