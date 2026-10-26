"""The UI user manual's option table must agree with the dashboard command's help."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import re
import unittest

from experiment_craft import cli

PROJECT = Path(__file__).resolve().parents[1]
MANUAL = PROJECT / 'docs' / 'ui-user-manual.md'


def dashboard_help():
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            cli.main(['dashboard', '--help'])
        except SystemExit:
            pass
    return out.getvalue()


def option_rows():
    """Rows of the manual's command option table: (option and metavar, description)."""
    section = MANUAL.read_text().split('## Command options', 1)[1].split('\n## ', 1)[0]
    return re.findall(r'^\| `(--[^`]+)` \| (.*) \|$', section, flags=re.M)


class CommandOptions(unittest.TestCase):
    def test_the_table_lists_exactly_the_dashboard_options(self):
        listed = {option for option, _ in option_rows()}
        shown = set(re.findall(r'^  (--[a-z-]+(?: [A-Z]+)?)', dashboard_help(), flags=re.M)) - {'--help'}
        self.assertEqual(listed, shown)

    def test_the_table_defaults_match_the_help(self):
        help_text = ' '.join(dashboard_help().split())
        for option, description in option_rows():
            default = re.match(r'`([^`]+)`;', description)
            if default:
                name = option.split()[0]
                self.assertRegex(help_text, re.escape(name) + r' N (?:(?! --).)*\(default: ' + re.escape(default.group(1)) + r'\)',
                                 option)


if __name__ == '__main__':
    unittest.main()
