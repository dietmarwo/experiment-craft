"""Source drift must be caught before a reproduction build can start."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('baseline', Path(__file__).resolve().parents[1] / 'scripts/baseline.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

PIN = 'a' * 40
OTHER = 'b' * 40
SOURCE = 'git+https://github.com/dietmarwo/optimization-jobs?rev={0}#{0}'


def git(root, *args):
    subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)


def commit(root, message):
    git(root, 'add', '-A')
    git(root, '-c', 'user.name=Baseline Test', '-c', 'user.email=baseline@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', message)
    return baseline.git(root, 'rev-parse', 'HEAD')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        self.root.mkdir()
        git(self.root, 'init', '-q')
        # Allow fetching a commit that is not a branch tip, as GitHub does.
        git(self.root, 'config', 'uploadpack.allowAnySHA1InWant', 'true')


class SourceLock(Fixture):
    def setUp(self):
        super().setUp()
        (self.root / 'Cargo.lock').write_text('locked dependency fixture\n')
        self.entry = {'commit': commit(self.root, 'fixture'),
                      'files_sha256': {'Cargo.lock': baseline.digest(self.root / 'Cargo.lock')}}

    def test_exact_clean_revision_is_accepted(self):
        baseline.verify_repo(self.root, self.entry)

    def test_fetch_creates_exact_detached_checkout(self):
        destination = Path(self.temp.name) / 'fetched'
        self.entry['url'] = str(self.root)
        baseline.fetch_repo(destination, self.entry)
        baseline.verify_repo(destination, self.entry)
        detached = subprocess.run(['git', '-C', str(destination), 'symbolic-ref', '-q', 'HEAD'],
                                  capture_output=True)
        self.assertNotEqual(detached.returncode, 0)

    def test_lockfile_edit_is_rejected_and_preserved(self):
        path = self.root / 'Cargo.lock'
        path.write_text('user changes\n')
        with self.assertRaisesRegex(ValueError, 'not clean'):
            baseline.fetch_repo(self.root, self.entry)
        self.assertEqual(path.read_text(), 'user changes\n')

    def test_wrong_revision_is_rejected(self):
        self.entry['commit'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'HEAD differs'):
            baseline.verify_repo(self.root, self.entry)

    def test_wrong_checksum_is_rejected(self):
        self.entry['files_sha256']['Cargo.lock'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum differs'):
            baseline.verify_repo(self.root, self.entry)

    def test_untracked_source_is_rejected(self):
        (self.root / 'unexpected.rs').write_text('fn main() {}\n')
        with self.assertRaisesRegex(ValueError, 'not clean'):
            baseline.verify_repo(self.root, self.entry)

    def test_incomplete_checkout_is_reported_and_kept(self):
        partial = Path(self.temp.name) / 'partial'
        git(Path(self.temp.name), 'init', '-q', str(partial))
        with self.assertRaisesRegex(ValueError, 'not a complete checkout'):
            baseline.fetch_repo(partial, self.entry)
        self.assertTrue((partial / '.git').is_dir())


class WorkerPin(Fixture):
    def write(self, manifest_rev, lock_rev, tutorial_lock=None):
        dependency = 'optimization-job-api = {{ git = "https://github.com/dietmarwo/optimization-jobs", rev = "{}" }}\n'
        (self.root / 'Cargo.toml').write_text('[workspace.dependencies]\n' + dependency.format(manifest_rev))
        (self.root / 'Cargo.lock').write_text(
            f'[[package]]\nname = "optimization-job-api"\nsource = "{SOURCE.format(lock_rev)}"\n')
        if tutorial_lock:
            (self.root / 'tutorial').mkdir()
            (self.root / 'tutorial/Cargo.lock').write_text(f'source = "{tutorial_lock}"\n')
        commit(self.root, 'pins')
        return {'contracts': {'worker_job_api_revision': PIN},
                'repositories': {'optimization-jobs': {}, 'source': {'job_api_revision': PIN}}}

    def test_matching_pin_is_accepted(self):
        baseline.verify_pins(Path(self.temp.name), self.write(PIN, PIN))

    def test_manifest_with_another_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cargo.toml files pin'):
            baseline.verify_pins(Path(self.temp.name), self.write(OTHER, PIN))

    def test_lockfile_with_another_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cargo.lock'):
            baseline.verify_pins(Path(self.temp.name), self.write(PIN, OTHER))

    def test_nested_lockfile_on_a_branch_is_rejected(self):
        branch = 'git+https://github.com/dietmarwo/optimization-jobs?branch=main#' + PIN
        with self.assertRaisesRegex(ValueError, 'tutorial/Cargo.lock'):
            baseline.verify_pins(Path(self.temp.name), self.write(PIN, PIN, tutorial_lock=branch))

    def test_lock_entry_inconsistent_with_contract_is_rejected(self):
        lock = self.write(PIN, PIN)
        lock['repositories']['source']['job_api_revision'] = OTHER
        with self.assertRaisesRegex(ValueError, 'baseline-lock.json'):
            baseline.verify_pins(Path(self.temp.name), lock)


class SharedPaths(Fixture):
    paths = ['crates', 'Cargo.lock']

    def setUp(self):
        super().setUp()
        (self.root / 'crates').mkdir()
        (self.root / 'crates/lib.rs').write_text('pub fn f() {}\n')
        (self.root / 'README.md').write_text('readme\n')
        self.pin = commit(self.root, 'pin')

    def test_unshared_change_is_accepted(self):
        (self.root / 'README.md').write_text('tutorial added\n')
        commit(self.root, 'docs')
        self.assertEqual(baseline.shared_changes(self.root, self.pin, self.paths), [])

    def test_shared_change_is_reported(self):
        (self.root / 'crates/lib.rs').write_text('pub fn g() {}\n')
        commit(self.root, 'api change')
        self.assertEqual(baseline.shared_changes(self.root, self.pin, self.paths), ['crates/lib.rs'])

    def test_missing_pin_object_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'not fetched'):
            baseline.shared_changes(self.root, OTHER, self.paths)

    def test_depth_one_checkout_with_fetched_pin(self):
        (self.root / 'README.md').write_text('tutorial added\n')
        head = commit(self.root, 'docs')
        clone = Path(self.temp.name) / 'clone'
        baseline.fetch_repo(clone, {'url': 'file://' + str(self.root), 'commit': head, 'files_sha256': {}})
        self.assertFalse(baseline.has_commit(clone, self.pin))
        baseline.fetch_commit(clone, self.pin)
        self.assertEqual(baseline.shared_changes(clone, self.pin, self.paths), [])


class Staging(unittest.TestCase):
    def test_binaries_are_copied_with_digests(self):
        with tempfile.TemporaryDirectory() as temp:
            target, destination = Path(temp) / 'release', Path(temp) / 'bin'
            target.mkdir()
            (target / 'tool').write_bytes(b'binary')
            staged = baseline.stage_binaries(target, destination, ['tool'])
            (target / 'tool').write_bytes(b'rebuilt by a later check')
            self.assertEqual((destination / 'tool').read_bytes(), b'binary')
            self.assertEqual(staged['tool']['sha256'], baseline.digest(destination / 'tool'))

    def test_missing_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'missing built executable'):
                baseline.stage_binaries(Path(temp), Path(temp) / 'bin', ['tool'])


class StagedManifest(unittest.TestCase):
    lock = {'repositories': {'optimization-jobs': {'commit': PIN, 'files_sha256': {}},
                             'w': {'commit': OTHER, 'files_sha256': {}, 'worker_package': 'w-worker'}}}

    def stage(self, bins):
        target = bins.parent / 'release'
        target.mkdir()
        for name in baseline.binary_names(self.lock):
            (target / name).write_bytes(name.encode())
        files = baseline.stage_binaries(target, bins, baseline.binary_names(self.lock))
        baseline.write_json(bins / 'manifest.json', {'toolchain': '1.88.0', 'files': files,
                                                     'sources': {'optimization-jobs': PIN, 'w': OTHER}})

    def test_unchanged_staged_executables_are_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            bins = Path(temp) / 'bin'
            self.stage(bins)
            self.assertEqual(baseline.staged_manifest(bins, self.lock)['toolchain'], '1.88.0')

    def test_replaced_executable_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            bins = Path(temp) / 'bin'
            self.stage(bins)
            (bins / 'w-worker').write_bytes(b'other build')
            with self.assertRaisesRegex(ValueError, 'changed since it was staged'):
                baseline.staged_manifest(bins, self.lock)

    def test_executables_from_other_commits_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            bins = Path(temp) / 'bin'
            self.stage(bins)
            lock = {'repositories': {**self.lock['repositories'],
                                     'w': {'commit': PIN, 'files_sha256': {}, 'worker_package': 'w-worker'}}}
            with self.assertRaisesRegex(ValueError, 'other commits'):
                baseline.staged_manifest(bins, lock)

    def test_smoke_without_staged_executables_records_an_error(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = {'toolchain': {'rust': {'build': '1.88.0', 'lint': 'stable'}},
                    'contracts': {'worker_job_api_revision': PIN}, **self.lock}
            output = Path(temp) / 'evidence'
            args = argparse.Namespace(
                actions=['smoke'], workspace=Path(temp), output=output, jobs=1,
                build_toolchain=None, lint_toolchain=None)
            original = baseline.verify_project, baseline.prepare_sources
            baseline.verify_project, baseline.prepare_sources = (lambda lock: None), (lambda *a: {})
            try:
                with self.assertRaisesRegex(ValueError, 'run the build action first'):
                    baseline.run(args, lock)
            finally:
                baseline.verify_project, baseline.prepare_sources = original
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['status'], 'error')
            # An existing evidence directory is never reused.
            baseline.verify_project, baseline.prepare_sources = (lambda lock: None), (lambda *a: {})
            try:
                with self.assertRaises(FileExistsError):
                    baseline.run(args, lock)
            finally:
                baseline.verify_project, baseline.prepare_sources = original


class Actions(unittest.TestCase):
    def test_actions_run_in_dependency_order(self):
        self.assertEqual(baseline.selected(['smoke', 'build']), ['build', 'smoke'])
        self.assertEqual(baseline.selected(['all']), ['fetch', 'build', 'smoke', 'check'])


if __name__ == '__main__':
    unittest.main()
