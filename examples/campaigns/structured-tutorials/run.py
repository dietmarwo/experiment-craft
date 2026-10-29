#!/usr/bin/env python3
"""Twenty application command jobs plus four supported native comparison jobs."""

import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))
from experiment_craft.campaign import initialize, drive
from experiment_craft.manifest import compile_manifest
from experiment_craft.comparison import declare
from experiment_craft.comparison_report import report as compare
from experiment_craft.report import report
from experiment_craft.storage import Store


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sources", type=Path, default=PROJECT.parent)
    p.add_argument("--bin-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    source.mkdir()
    sources = args.sources.resolve()
    bindir = args.bin_dir.resolve()
    runner = bindir / "optimization-run"
    node = out / "node"
    spec = importlib.util.spec_from_file_location(
        "structured_driver", sources / "optimization-jobs/tutorials/structured/run.py"
    )
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    steps = []
    for chapter in driver.ORDER:
        folder = source / chapter
        folder.mkdir()
        job = driver.command_spec(sources, chapter, "smoke", folder)
        job.pop("request_key")
        for item in job["inputs"]:
            item["file"] = chapter + "/" + item["file"]
        steps.append(dict(id=chapter, job=job))
    # A dependent checker consumes checked native command outputs, not mutable work files.
    check = source / "check.py"
    check.write_text(
        "import json\nfrom pathlib import Path\nfiles=sorted(Path('results').glob('*.json'))\nassert len(files)==20\nfor p in files:\n d=json.loads(p.read_text());assert d['chapter']==p.stem\nPath('checks.json').write_text(json.dumps({'checked_summaries':len(files)}))\n"
    )
    inputs = [dict(path="check.py", file="check.py")] + [
        dict(
            path="results/" + c + ".json",
            **{"from": dict(step=c, kind="output", output="summary")},
        )
        for c in driver.ORDER
    ]
    steps.append(
        dict(
            id="application-checks",
            job=dict(
                schema_version="execution.command/0.1",
                argv=[sys.executable, "check.py"],
                env={},
                resources=dict(cpu_slots=1),
                limits=dict(wall_seconds=30, grace_seconds=1),
                replay="never",
                inputs=inputs,
                outputs=[
                    dict(
                        name="checks",
                        path="checks.json",
                        required=True,
                        max_bytes=10000,
                    )
                ],
            ),
        )
    )
    sys.path.insert(0, str(sources / "LP-IP-craft/tutorials/_support"))
    from linear_model import LinearModel

    m = LinearModel("maximize")
    v = [m.var(n, c, kind="binary") for n, c in zip("ABC", [9, 8, 7])]
    m.row("budget", dict(zip(v, [6, 5, 4])), upper=10)
    (source / "allocation-model.json").write_text(json.dumps(m.artifact()))
    for on in [True, False]:
        job = json.loads((PROJECT / "examples/smoke/lp-ip/job.json").read_text())
        job.pop("request_key", None)
        job["payload"].update(starts=[None], presolve=on)
        job["inputs"] = [dict(name="model", file="allocation-model.json")]
        steps.append(dict(id="lp-on" if on else "lp-off", job=job))
    for backend in ["active_set", "clarabel"]:
        job = json.loads((PROJECT / "examples/smoke/sqp/job.json").read_text())
        job.pop("request_key", None)
        job["payload"].update(backend=backend, starts=[[0.1, 0.2, 0.3, 0.4]])
        steps.append(dict(id="sqp-" + backend, job=job))
    manifest = dict(
        schema_version="experiment.campaign/0.1",
        name="Twenty structured tutorials and supported native comparisons",
        allow_commands=True,
        budget=dict(
            max_jobs=25, max_wall_seconds=1800, max_reserved_slot_seconds=20000
        ),
        steps=steps,
    )
    manifest_path = source / "campaign.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    plan = compile_manifest(manifest_path)
    groups = []
    for profile, ids, pointer in [
        ("lp", ["lp-on", "lp-off"], "/payload/presolve"),
        ("sqp", ["sqp-active_set", "sqp-clarabel"], "/payload/backend"),
    ]:
        groups.append(
            dict(
                id=profile,
                description="Same model and starts, supported settings only; pipeline check",
                kind="optimization",
                arms=[dict(id=c, templates=[c]) for c in ids],
                vary=[pointer],
                replication=dict(kind="deterministic"),
                design="unpaired",
                budget=dict(
                    kind="fixed_time",
                    seconds=steps[-1]["job"]["limits"]["wall_time_seconds"]
                    if profile == "sqp"
                    else steps[-3]["job"]["limits"]["wall_time_seconds"],
                ),
                metrics=[
                    dict(
                        id="objective",
                        pointer="/outcome/objective",
                        unit="native model objective",
                        direction="none",
                    )
                ],
            )
        )
    protocol = dict(
        schema_version="experiment.comparison/0.1",
        name="Supported native comparisons; application reports remain command artifacts",
        plan_id=plan["plan_id"],
        groups=groups,
        exclude=[
            dict(
                template=c,
                reason="Application command output; no inferred solver metrics",
            )
            for c in driver.ORDER + ["application-checks"]
        ],
    )
    protocol_path = source / "comparison.json"
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    driver.call(
        [runner, "--root", node, "node", "init", "--capacity", "2", "--allow-commands"]
    )
    for worker, binary in [("lp-ip", "lp-ip-job-worker"), ("sqp", "sqp-job-worker")]:
        driver.call(
            [
                runner,
                "--root",
                node,
                "workers",
                "add",
                "--id",
                worker,
                "--executable",
                bindir / binary,
            ]
        )
    initialize(manifest_path, out / "campaign", runner, node, "foreground")
    with closing(Store(out / "campaign")) as store:
        declare(store, protocol_path)
        outcome = drive(store)
        assert outcome["status"] == "completed", outcome
        report(store, out / "report")
        compare(store, out / "comparison")
    (out / "summary.json").write_text(
        json.dumps(
            dict(
                jobs=25,
                applications=20,
                native_comparisons=4,
                dependent_checker=1,
                status="passed",
                campaign=outcome,
            ),
            indent=2,
        )
        + "\n"
    )
    print("25 jobs passed; 20 application reports and 2 native comparison groups")


if __name__ == "__main__":
    main()
