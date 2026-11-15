#!/usr/bin/env python3
"""Seeds × optimizers, followed by a dependent CLI replay of sealed winners."""
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
from experiment_craft.campaign import initialize, drive
from experiment_craft.manifest import compile_manifest
from experiment_craft.report import report
from experiment_craft.storage import Store


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sources", type=Path, default=PROJECT.parent)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--evaluator", default="hydro-craft")
    p.add_argument("--preset", choices=["smoke", "study"], default="smoke")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seeds", help="comma-separated nonnegative seeds; default from preset")
    p.add_argument("--evals", type=int, help="override evaluation budget per arm")
    p.add_argument("--runner", type=Path)
    args = p.parse_args()
    if not 1 <= args.workers <= 8:
        raise ValueError("workers must be 1..8")
    sources, out = args.sources.resolve(), args.output.resolve()
    shared = sources / "optimization-jobs/tutorials/domain-evaluators"
    sys.path.insert(0, str(shared))
    spec = importlib.util.spec_from_file_location("domain_driver", shared / "run.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    descriptor = driver.load(sources, args.evaluator)[2]
    preset = descriptor["presets"][args.preset]
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else preset["seeds"]
    evaluations = args.evals if args.evals is not None else preset["evals"]
    if not seeds or len(set(seeds)) != len(seeds) or min(seeds) < 0 or evaluations < 1:
        raise ValueError("distinct nonnegative seeds and positive evals required")
    if len(seeds) * len(descriptor["optimizers"]) > 32:
        raise ValueError("tutorial is bounded to 32 search arms")
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    source.mkdir()
    steps, expected = [], []
    for optimizer in descriptor["optimizers"]:
        for seed in seeds:
            name = f"{optimizer}-{seed}"
            folder = source / name
            driver.stage(sources, args.evaluator, folder)
            job = driver.search_spec(folder, seed, evaluations, optimizer, args.workers)
            for item in job["inputs"]:
                item["file"] = name + "/" + item["file"]
            steps.append(dict(id=name, job=job))
            expected.append(dict(id=name, optimizer=optimizer, seed=seed, budget=evaluations))
    folder = source / "checker"
    driver.stage(sources, args.evaluator, folder)
    shutil.copyfile(Path(__file__).with_name("check.py"), folder / "campaign_check.py")
    driver.write(folder / "expected.json", expected)
    checks = driver.command_spec(folder, ["campaign_check.py"], {"checks": "checks.json"}, 1,
                                 wall=max(60, len(expected) * 10))
    for item in checks["inputs"]:
        item["file"] = "checker/" + item["file"]
    checks["inputs"] += [dict(path="winners/" + arm["id"] + ".json",
                              **{"from": dict(step=arm["id"], kind="output", output="best")}) for arm in expected]
    steps.append(dict(id="check", needs=[a["id"] for a in expected], job=checks))
    manifest = json.loads(Path(__file__).with_name("manifest-template.json").read_text())
    manifest.update(name=args.evaluator + " seed and optimizer campaign", steps=steps)
    manifest["budget"] = dict(max_jobs=len(steps), max_wall_seconds=len(steps)*150 + 60,
                              max_reserved_slot_seconds=sum(s["job"]["resources"]["cpu_slots"] *
                                  (s["job"]["limits"]["wall_seconds"] + s["job"]["limits"]["grace_seconds"]) for s in steps))
    path = source / "campaign.json"
    driver.write(path, manifest)
    plan = compile_manifest(path)
    runner = (args.runner or sources / "optimization-jobs/target/release/optimization-run").resolve()
    node = out / "node"
    driver.call([runner, "--root", node, "node", "init", "--capacity", args.workers, "--allow-commands"])
    started = time.perf_counter()
    summary = dict(passed=False, evaluator=args.evaluator, seeds=seeds, evaluations=evaluations,
                   plan_id=plan["plan_id"], expected_arms=expected)
    try:
        initialize(path, out / "campaign", runner, node, "foreground")
        with closing(Store(out / "campaign")) as store:
            outcome = drive(store)
            report(store, out / "report")  # Keeps failed/blocked rows even if check cannot run.
            jobs = driver.call([runner, "--root", node, "jobs", "list"])
            repeated = drive(store)
            after = driver.call([runner, "--root", node, "jobs", "list"])
        unchanged = repeated == outcome and len(after) == len(jobs)
        summary.update(passed=outcome["status"] == "completed" and unchanged,
                       campaign=outcome, repeated_observation_unchanged=unchanged,
                       native_jobs=len(jobs))
        # Collect the final sealed check result, including a failed check's report.
        for job in jobs:
            execution = driver.call([runner, "--root", node, "result", job["directory"]])
            if "checks" in execution.get("outputs", {}):
                driver.call([runner, "--root", node, "jobs", "collect", job["id"], "checks",
                             "--destination", out / "checks.json"])
                summary["scientific_checks"] = json.loads((out / "checks.json").read_text())
    except Exception as error:
        summary.update(passed=False, error=str(error))
    summary["seconds"] = time.perf_counter() - started
    driver.write(out / "summary.json", summary)
    print(json.dumps({k:summary[k] for k in ["passed", "evaluator", "seconds"]}))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
