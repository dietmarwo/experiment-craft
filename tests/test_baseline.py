"""Source drift must be caught before a reproduction build can start."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('baseline', Path(__file__).resolve().parents[1] / 'scripts/baseline.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class SourceLock(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        self.root.mkdir()
        self.git('init', '-q')
        (self.root / 'Cargo.lock').write_text('locked dependency fixture\n')
        self.git('add', 'Cargo.lock')
        self.git('-c', 'user.name=Baseline Test', '-c', 'user.email=baseline@example.invalid', 'commit', '-qm', 'fixture')
        self.entry = {'commit': baseline.git(self.root, 'rev-parse', 'HEAD'),
                      'files_sha256': {'Cargo.lock': baseline.digest(self.root / 'Cargo.lock')}}

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)

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


if __name__ == '__main__':
    unittest.main()
