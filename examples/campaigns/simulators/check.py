"""Check sealed tutorial outputs and compare C1 work across CPU layouts."""

import json
from pathlib import Path


def signature(summary):
    return [
        (
            a["model"],
            a["route"],
            a["seed"],
            a["actual_evaluations"],
            a["search_work"],
            a["rates"],
            a["training_loss"],
            a["holdout_loss"],
        )
        for a in summary["arms"]
    ]


def main():
    expected = json.loads(Path("expected.json").read_text())
    rows = {p.stem: json.loads(p.read_text()) for p in Path("results").glob("*.json")}
    if sorted(rows) != sorted(expected):
        raise ValueError("missing or unexpected sealed summaries")
    if any(r.get("passed") is not True for r in rows.values()):
        raise ValueError("a numerical tutorial check failed")
    layouts = [(name, r) for name, r in rows.items() if name.startswith("layout-")]
    if not layouts:
        raise ValueError("no CPU-layout evidence")
    reference = [signature(r["summary"]) for r in layouts[0][1]["runs"]]
    for name, record in layouts:
        if record["outer"] * record["inner"] > record["cpu_slots"]:
            raise ValueError("CPU allowance exceeded: " + name)
        if [signature(r["summary"]) for r in record["runs"]] != reference:
            raise ValueError(
                "fixed work or numerical results changed across CPU layouts: " + name
            )
    report = dict(
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
    Path("checks.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
