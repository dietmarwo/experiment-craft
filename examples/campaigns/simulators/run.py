#!/usr/bin/env python3
"""X1: simulator tutorials and fixed-CPU layouts through the existing campaign API."""

import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))
from experiment_craft.campaign import initialize, drive  # noqa: E402
from experiment_craft.manifest import compile_manifest  # noqa: E402
from experiment_craft.report import report  # noqa: E402
from experiment_craft.storage import Store  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=PROJECT.parent)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", choices=["smoke", "study"], default="smoke")
    parser.add_argument("--cpu-slots", type=int, default=8)
    parser.add_argument("--tasks", type=int, default=8)
    parser.add_argument("--extend", action="store_true", help="also run C2 and F3")
    for option in [
        "crn-binary",
        "ode-binary",
        "reference-binary",
        "cfd-binary",
        "cfd-worker",
        "runner",
    ]:
        parser.add_argument("--" + option, type=Path)
    args = parser.parse_args()
    if args.cpu_slots not in [1, 2, 4, 8] or not 1 <= args.tasks <= 32:
        raise ValueError("use 1, 2, 4 or 8 CPU slots and 1..32 tasks")
    sources = args.sources.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location(
        "simulator_driver", sources / "optimization-jobs/tutorials/simulators/run.py"
    )
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    bins = driver.binary_options(args, sources)
    source = out / "source"
    source.mkdir()
    steps = []
    started = time.perf_counter()
    pairs = sorted(
        {
            (1, args.cpu_slots),
            (args.cpu_slots, 1),
            (min(2, args.cpu_slots), args.cpu_slots // min(2, args.cpu_slots)),
        }
    )
    for outer, inner in pairs:
        name = f"layout-{outer}x{inner}"
        folder = source / name
        folder.mkdir()
        job = driver.command_spec(
            sources,
            "C1",
            args.preset,
            folder,
            bins,
            layout=(outer, inner, args.tasks, args.cpu_slots),
        )
        for item in job["inputs"]:
            item["file"] = name + "/" + item["file"]
        steps.append(dict(id=name, job=job))
    for chapter in ["F1", "C2", "F3"] if args.extend else ["F1"]:
        folder = source / chapter
        folder.mkdir()
        job = driver.command_spec(
            sources, chapter, args.preset, folder, bins, threads=1
        )
        for item in job["inputs"]:
            item["file"] = chapter + "/" + item["file"]
        steps.append(dict(id=chapter, job=job))
    expected = [s["id"] for s in steps]
    (source / "expected.json").write_text(json.dumps(expected) + "\n")
    shutil.copyfile(Path(__file__).with_name("check.py"), source / "check.py")
    checks = dict(
        schema_version="execution.command/0.1",
        argv=[sys.executable, "check.py"],
        env={},
        resources=dict(cpu_slots=1),
        limits=dict(wall_seconds=30, grace_seconds=1),
        replay="never",
        inputs=[
            dict(path="check.py", file="check.py"),
            dict(path="expected.json", file="expected.json"),
        ]
        + [
            dict(
                path="results/" + name + ".json",
                **{"from": dict(step=name, kind="output", output="summary")},
            )
            for name in expected
        ],
        outputs=[
            dict(name="checks", path="checks.json", required=True, max_bytes=1048576)
        ],
    )
    steps.append(dict(id="numerical-and-work-checks", job=checks))
    manifest = dict(
        schema_version="experiment.campaign/0.1",
        name="CRN and CFD tutorials at a fixed local CPU budget",
        allow_commands=True,
        budget=dict(
            max_jobs=len(steps),
            max_wall_seconds=14400,
            max_reserved_slot_seconds=sum(
                s["job"]["resources"]["cpu_slots"]
                * (
                    s["job"]["limits"]["wall_seconds"]
                    + s["job"]["limits"]["grace_seconds"]
                )
                for s in steps
            ),
        ),
        steps=steps,
    )
    path = source / "campaign.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    plan = compile_manifest(path)
    node = out / "node"
    driver.call(
        [
            bins["runner"],
            "--root",
            node,
            "node",
            "init",
            "--capacity",
            args.cpu_slots,
            "--allow-commands",
        ]
    )
    initialize(path, out / "campaign", bins["runner"], node, "foreground")
    setup_seconds = time.perf_counter() - started
    with closing(Store(out / "campaign")) as store:
        outcome = drive(store)
        report(store, out / "report")
        # Re-observe a terminal campaign: native handles must not be resubmitted.
        observed = drive(store)
    passed = outcome["status"] == "completed" and observed == outcome
    result = dict(
        chapter="X1",
        passed=passed,
        plan_id=plan["plan_id"],
        campaign=outcome,
        repeated_observation_unchanged=observed == outcome,
        setup_seconds=setup_seconds,
        total_seconds=time.perf_counter() - started,
        source_identity=driver.source_identity(sources),
        packages=driver.packages(),
        cpu_slots=args.cpu_slots,
        tasks_per_layout=args.tasks,
        cold_build_seconds=None,
        scope="Local foreground command campaign. Cold installation/build is not included; record it independently. Native handles and sealed evidence remain in the campaign/node. No formal cross-profile comparison or distributed persistence claim.",
    )
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(passed=passed, status=outcome["status"], steps=outcome["steps"])
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
