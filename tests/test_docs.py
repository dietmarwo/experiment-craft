"""Relative links in the Markdown files must point at existing files and headings."""
from pathlib import Path
import re
import subprocess
import unittest

PROJECT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
IMAGE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"')


def tracked_markdown():
    listed = subprocess.run(['git', '-C', str(PROJECT), 'ls-files', '*.md'],
                            capture_output=True, text=True)
    if listed.returncode == 0 and listed.stdout.strip():
        return [PROJECT / name for name in listed.stdout.split()]
    return sorted(PROJECT.rglob('*.md'))


def without_code(text):
    return re.sub(r'```.*?```', '', text, flags=re.S)


def anchors(page):
    """Heading anchors as GitHub derives them: lowercase, punctuation dropped, spaces to hyphens."""
    seen, result = {}, set()
    for line in without_code(page.read_text()).splitlines():
        heading = re.match(r'#{1,6}\s+(.*?)\s*#*\s*$', line)
        if not heading:
            continue
        slug = re.sub(r'[^\w\- ]', '', heading.group(1).lower()).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if count == 0 else f'{slug}-{count}')
    return result


class RelativeLinks(unittest.TestCase):
    def test_relative_links_resolve(self):
        broken = []
        for page in tracked_markdown():
            text = without_code(page.read_text())
            for target in LINK.findall(text) + IMAGE.findall(text):
                if re.match(r'[a-z][a-z0-9+.-]*:', target):
                    continue
                path, _, fragment = target.partition('#')
                destination = page.parent / path if path else page
                if not destination.exists():
                    broken.append(f'{page.relative_to(PROJECT)}: {target}')
                elif fragment and destination.suffix == '.md' and fragment not in anchors(destination):
                    broken.append(f'{page.relative_to(PROJECT)}: {target} (no such heading)')
        self.assertEqual(broken, [])

    def test_anchor_rule(self):
        page = PROJECT / 'implementation-log.md'
        self.assertIn('p0--audit-and-pin-the-foundation', anchors(page))


if __name__ == '__main__':
    unittest.main()
