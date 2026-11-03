"""The X1 dependent check refuses missing, failed or layout-dependent work."""

import copy
import importlib.util
from pathlib import Path
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "simulator_check", PROJECT / "examples/campaigns/simulators/check.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def fit(threads, seed=7001):
    return dict(
        passed=True,
        budgets=dict(threads=threads),
        arms=[
            dict(
                model="binding",
                fast=True,
                route="reusable",
                seed=seed,
                actual_evaluations=32,
                search_work=dict(events=100, paths=512),
                validation_work=dict(events=50, paths=2080),
                rates=[0.4, 0.2],
                training_loss=0.01,
                holdout_loss=0.02,
            )
        ],
    )


def layout(outer, inner, tasks=2):
    return dict(
        passed=True,
        outer=outer,
        inner=inner,
        cpu_slots=outer * inner,
        tasks=tasks,
        total_seconds=1.0,
        runs=[dict(index=i, summary=fit(inner, 7001 + 100 * i)) for i in range(tasks)],
    )


def campaign():
    return {
        "layout-1x2": layout(1, 2),
        "layout-2x1": layout(2, 1),
        "F1": dict(passed=True),
    }


class SimulatorCampaignCheck(unittest.TestCase):
    def test_equal_work_passes(self):
        rows = campaign()
        report = checker.check(sorted(rows), rows)
        self.assertTrue(report["identical_C1_work_and_results"])
        self.assertEqual([r["name"] for r in report["layouts"]], sorted(rows)[1:])

    def test_missing_summary_is_refused(self):
        rows = campaign()
        with self.assertRaisesRegex(ValueError, "missing or unexpected"):
            checker.check(sorted(rows) + ["F3"], rows)

    def test_failed_step_is_named(self):
        rows = campaign()
        rows["F1"]["passed"] = False
        with self.assertRaisesRegex(ValueError, "checks failed: F1"):
            checker.check(sorted(rows), rows)

    def test_changed_validation_work_names_the_layout(self):
        rows = campaign()
        arm = rows["layout-2x1"]["runs"][1]["summary"]["arms"][0]
        arm["validation_work"] = dict(events=51, paths=2080)
        with self.assertRaisesRegex(ValueError, "between layout-2x1 and layout-1x2"):
            checker.check(sorted(rows), rows)

    def test_task_threads_must_match_the_layout(self):
        rows = campaign()
        rows["layout-1x2"]["runs"][0]["summary"]["budgets"]["threads"] = 99
        with self.assertRaisesRegex(ValueError, "99 threads, not 2"):
            checker.check(sorted(rows), rows)

    def test_task_without_summary_is_refused(self):
        rows = campaign()
        broken = copy.deepcopy(rows)
        broken["layout-2x1"]["runs"][0]["summary"] = None
        with self.assertRaisesRegex(ValueError, "task 0 has no summary"):
            checker.check(sorted(broken), broken)

    def test_oversubscribed_layout_is_refused(self):
        rows = campaign()
        rows["layout-2x1"]["cpu_slots"] = 1
        with self.assertRaisesRegex(ValueError, "CPU allowance exceeded"):
            checker.check(sorted(rows), rows)


if __name__ == "__main__":
    unittest.main()
