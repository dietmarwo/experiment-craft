"""Dependent scientific check: read sealed winners and replay all arms."""
import json
from pathlib import Path
import check as replay
from support import write


def main():
    expected = json.loads(Path("expected.json").read_text())
    case = json.loads(Path("case.json").read_text())
    rows = []
    for arm in expected:
        row = dict(id=arm["id"], passed=False)
        try:
            best = json.loads((Path("winners") / (arm["id"] + ".json")).read_text())
            if any(best[key] != arm[key] for key in ["seed", "optimizer", "budget"]):
                raise ValueError("winner does not match expected arm")
            folder = Path("replays") / arm["id"]
            folder.mkdir(parents=True)
            row.update(replay.check(best, case, "binary", folder))
        except Exception as error:
            row["error"] = str(error)
        rows.append(row)
    result = dict(passed=bool(rows) and all(r["passed"] for r in rows), rows=rows,
                  interpretation="Descriptive model results, no formal scientific-comparison adapter or optimality claim. Failed rows are retained.")
    write("checks.json", result)
    if not result["passed"]:
        raise ValueError("one or more scientific checks failed; inspect checks.json")


if __name__ == "__main__":
    main()
