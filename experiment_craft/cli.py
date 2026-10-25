"""The experiment-craft CLI emits JSON; expected errors use stable codes."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from . import __version__
from .campaign import collect_now, drive, initialize, request_stop, summary
from .manifest import compile_manifest, scientific
from .report import diff, report
from .storage import Error, Store, canonical, read_json


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Error('invalid_command', message)


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--version', action='version', version=__version__)
        sub = parser.add_subparsers(dest='command', required=True)
        dry = sub.add_parser('dry-run', help='pure deterministic expansion; no runtime calls or writes')
        dry.add_argument('manifest', type=Path)
        for command in ['init', 'run']:
            p = sub.add_parser(command)
            p.add_argument('manifest', type=Path)
            p.add_argument('--workspace', type=Path, required=True)
            p.add_argument('--runner', type=Path, required=True)
            p.add_argument('--node-root', type=Path, required=True)
            p.add_argument('--mode', choices=['systemd', 'foreground'], default='systemd')
            if command == 'run':
                p.add_argument('--once', action='store_true')
        for command in ['continue', 'status', 'stop', 'collect', 'report', 'events']:
            p = sub.add_parser(command)
            p.add_argument('--workspace', type=Path, required=True)
            if command == 'continue':
                p.add_argument('--once', action='store_true')
            if command == 'events':
                p.add_argument('--after', type=int, default=0)
                p.add_argument('--limit', type=int, default=1000)
            if command == 'report':
                p.add_argument('--destination', type=Path, required=True)
        p = sub.add_parser('provenance-diff')
        p.add_argument('before', type=Path)
        p.add_argument('after', type=Path)
        args = parser.parse_args(argv)
        if args.command == 'dry-run':
            value = scientific(compile_manifest(args.manifest))
        elif args.command == 'provenance-diff':
            value = {'changes': diff(read_json(args.before), read_json(args.after))}
        elif args.command == 'init':
            value = initialize(args.manifest, args.workspace, args.runner, args.node_root, args.mode)
        else:
            if args.command == 'run':
                initialize(args.manifest, args.workspace, args.runner, args.node_root, args.mode)
            with closing(Store(args.workspace)) as store:
                if args.command in ['run', 'continue']:
                    value = drive(store, once=args.once)
                elif args.command == 'status':
                    value = summary(store.read())
                elif args.command == 'stop':
                    value = request_stop(store)
                elif args.command == 'collect':
                    value = collect_now(store)
                elif args.command == 'events':
                    value = {'events': store.events(args.after, args.limit)}
                else:
                    value = report(store, args.destination)
        print(canonical(value).decode())
        if args.command in ['run', 'continue'] and not args.once and value['status'] != 'completed':
            return 1
        return 0
    except (Error, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(canonical({'error': {'code': getattr(exc, 'code', 'campaign_error'), 'message': str(exc)}}).decode(), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # Decisions are transactional; an issued job keeps running natively
        # unless the interrupt reached the runner too. continue observes it.
        print(canonical({'error': {'code': 'interrupted', 'message': 'interrupted; continue observes issued jobs'}}).decode(),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
