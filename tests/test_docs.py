"""Relative links in the Markdown files must point at files in the repository."""
from pathlib import Path
import re
import subprocess
import unittest

PROJECT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')


def tracked_markdown():
    listed = subprocess.run(['git', '-C', str(PROJECT), 'ls-files', '*.md'],
                            capture_output=True, text=True)
    if listed.returncode == 0 and listed.stdout.strip():
        return [PROJECT / name for name in listed.stdout.split()]
    return sorted(PROJECT.rglob('*.md'))


class RelativeLinks(unittest.TestCase):
    def test_relative_links_resolve(self):
        broken = []
        for page in tracked_markdown():
            text = re.sub(r'```.*?```', '', page.read_text(), flags=re.S)
            for target in LINK.findall(text):
                if re.match(r'[a-z][a-z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                path = target.split('#', 1)[0]
                if not (page.parent / path).exists():
                    broken.append(f'{page.relative_to(PROJECT)}: {target}')
        self.assertEqual(broken, [])


if __name__ == '__main__':
    unittest.main()
