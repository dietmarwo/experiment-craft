"""Source drift must be caught before a reproduction build can start."""
import importlib.util
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
        'commit', '-qm', message)
    return baseline.git(root, 'rev-parse', 'HEAD')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        self.root.mkdir()
        git(self.root, 'init', '-q')


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
    def write(self, manifest_rev, lock_rev):
        (self.root / 'Cargo.toml').write_text(
            '[workspace.dependencies]\n'
            f'optimization-job-api = {{ git = "https://github.com/dietmarwo/optimization-jobs", rev = "{manifest_rev}" }}\n'
            f'optimization-runner = {{ git = "https://github.com/dietmarwo/optimization-jobs", rev = "{manifest_rev}" }}\n')
        (self.root / 'Cargo.lock').write_text(
            f'[[package]]\nname = "optimization-job-api"\nsource = "{SOURCE.format(lock_rev)}"\n')
        return {'contracts': {'worker_job_api_revision': PIN},
                'repositories': {'optimization-jobs': {}, 'source': {'job_api_revision': PIN}}}

    def test_matching_pin_is_accepted(self):
        baseline.verify_pins(Path(self.temp.name), self.write(PIN, PIN))

    def test_manifest_with_another_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cargo.toml'):
            baseline.verify_pins(Path(self.temp.name), self.write(OTHER, PIN))

    def test_lockfile_with_another_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cargo.lock'):
            baseline.verify_pins(Path(self.temp.name), self.write(PIN, OTHER))


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


class Actions(unittest.TestCase):
    def test_actions_run_in_dependency_order(self):
        self.assertEqual(baseline.selected(['smoke', 'build']), ['build', 'smoke'])
        self.assertEqual(baseline.selected(['all']), ['fetch', 'build', 'smoke', 'check'])


if __name__ == '__main__':
    unittest.main()
