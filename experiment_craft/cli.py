"""The experiment-craft CLI emits JSON; expected errors use stable codes."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from . import __version__
from .artifacts import catalog as artifact_catalog, collect as collect_artifact
from .campaign import collect_now, drive, initialize, request_stop, summary
from .comparison import declare
from .comparison_report import report as comparison_report
from .deployment import export as deployment_export, load as deployment_load, plan as deployment_plan, select as deployment_select
from .manifest import compile_manifest, scientific
from .report import diff, report
from .operations import backup, check_workspace, pause, restore, unpause
from .storage import Error, Store, canonical, read_json, require
from .verification import report as verification_report


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Error('invalid_command', message)


def main(argv=None):
    try:
        parser = Parser(prog='experiment-craft', description=__doc__)
        parser.add_argument('--version', action='version', version=__version__)
        sub = parser.add_subparsers(dest='command', required=True)
        p = sub.add_parser('dashboard', help='local browser controls and persisted per-node progress')
        p.add_argument('--workspace', type=Path, action='append', required=True, metavar='PATH',
                       help='an initialized campaign workspace; repeat for up to 32')
        p.add_argument('--state-dir', type=Path, required=True, metavar='PATH',
                       help='chart history, outside every campaign and node root; one dashboard at a time')
        p.add_argument('--deployment', type=Path, metavar='FILE', help='node inventory for labels and planned workers')
        p.add_argument('--port', type=int, default=8765, metavar='N',
                       help='port on 127.0.0.1; 0 picks a free one (default: %(default)s)')
        p.add_argument('--sample-seconds', type=float, default=2, metavar='N',
                       help='saved-state sampling interval, 0.25 to 60 (default: %(default)s)')
        p.add_argument('--history-limit', type=int, default=2000, metavar='N',
                       help='points kept per node and campaign set, 10 to 10000 (default: %(default)s)')
        dry = sub.add_parser('dry-run', help='pure deterministic expansion; no runtime calls or writes')
        dry.add_argument('manifest', type=Path)
        for command in ['init', 'run']:
            p = sub.add_parser(command)
            p.add_argument('manifest', type=Path)
            p.add_argument('--workspace', type=Path, required=True)
            p.add_argument('--runner', type=Path)
            p.add_argument('--node-root', type=Path)
            p.add_argument('--mode', choices=['systemd', 'foreground'])
            p.add_argument('--deployment', type=Path)
            p.add_argument('--node', help='explicit inventory node; defaults to the local test node')
            if command == 'run':
                p.add_argument('--once', action='store_true')
        p = sub.add_parser('declare-comparison', help='seal a scientific design before any dispatch')
        p.add_argument('protocol', type=Path)
        p.add_argument('--workspace', type=Path, required=True)
        for command in ['artifacts', 'collect-artifact', 'verification-report']:
            p = sub.add_parser(command, help='named command outputs and offline application-reported verification')
            p.add_argument('--workspace', type=Path, required=True)
            p.add_argument('--step', required=command != 'artifacts')
            if command != 'artifacts':
                p.add_argument('--output', required=command == 'collect-artifact', default='acceptance')
            else:
                p.add_argument('--after', type=int, default=0)
                p.add_argument('--limit', type=int, default=1000)
            if command == 'verification-report':
                p.add_argument('--adapter', default='cap.audit/0.1')
                p.add_argument('--destination', type=Path, required=True)
        for command in ['deployment-check', 'deployment-export']:
            p = sub.add_parser(command, help='offline configuration only; never executes native commands')
            p.add_argument('config', type=Path)
            if command == 'deployment-export':
                p.add_argument('--destination', type=Path, required=True)
        p = sub.add_parser('workspace-check', help="compare a workspace's database with its own records; "
                           'offline, never opens the database in place')
        p.add_argument('--workspace', type=Path, required=True)
        p = sub.add_parser('restore', help='restore into a new paused workspace without runtime calls')
        p.add_argument('archive', type=Path)
        p.add_argument('--workspace', type=Path, required=True)
        p.add_argument('--max-bytes', type=int, default=1024 ** 3)
        for command in ['continue', 'status', 'stop', 'collect', 'report', 'events', 'compare',
                        'pause-dispatch', 'unpause-dispatch', 'maintenance-status', 'backup']:
            p = sub.add_parser(command)
            p.add_argument('--workspace', type=Path, required=True)
            if command == 'continue':
                p.add_argument('--once', action='store_true')
            if command == 'events':
                p.add_argument('--after', type=int, default=0)
                p.add_argument('--limit', type=int, default=1000)
            if command in ['report', 'compare']:
                p.add_argument('--destination', type=Path, required=True)
            if command == 'pause-dispatch':
                p.add_argument('--reason', default='operator')
            if command == 'backup':
                p.add_argument('--destination', type=Path, required=True)
                p.add_argument('--max-bytes', type=int, default=1024 ** 3)
        p = sub.add_parser('provenance-diff')
        p.add_argument('before', type=Path)
        p.add_argument('after', type=Path)
        args = parser.parse_args(argv)
        if args.command in ['init', 'run']:
            args.command_policy = True
            if args.deployment:
                require(not args.runner and not args.node_root, 'invalid_command',
                        'use deployment selection or runner/node-root, not both')
                args.runner, args.node_root, args.mode, args.command_policy = deployment_select(args.deployment, args.node, args.mode)
            else:
                require(args.runner is not None and args.node_root is not None and args.node is None,
                        'invalid_command', 'provide runner and node-root, or deployment')
                args.mode = args.mode or 'systemd'
        if args.command == 'dashboard':
            from .dashboard import serve
            value = serve(args.workspace, args.state_dir, args.deployment, args.port, args.sample_seconds, args.history_limit)
        elif args.command == 'dry-run':
            value = scientific(compile_manifest(args.manifest))
        elif args.command == 'provenance-diff':
            value = {'changes': diff(read_json(args.before), read_json(args.after))}
        elif args.command == 'deployment-check':
            value = deployment_plan(deployment_load(args.config))
        elif args.command == 'deployment-export':
            value = deployment_export(args.config, args.destination)
        elif args.command == 'restore':
            value = restore(args.archive, args.workspace, args.max_bytes)
        elif args.command == 'workspace-check':
            value = check_workspace(args.workspace)
        elif args.command == 'init':
            value = initialize(args.manifest, args.workspace, args.runner, args.node_root, args.mode, args.command_policy)
        else:
            if args.command == 'run':
                initialize(args.manifest, args.workspace, args.runner, args.node_root, args.mode, args.command_policy)
            with closing(Store(args.workspace)) as store:
                if args.command in ['run', 'continue']:
                    value = drive(store, once=args.once)
                elif args.command == 'status':
                    value = summary(store.read())
                elif args.command == 'stop':
                    value = request_stop(store)
                elif args.command == 'collect':
                    value = collect_now(store)
                elif args.command == 'artifacts':
                    value = artifact_catalog(store, args.step, args.after, args.limit)
                elif args.command == 'collect-artifact':
                    value = collect_artifact(store, args.step, args.output)
                elif args.command == 'verification-report':
                    value = verification_report(store, args.destination, args.step, args.output, args.adapter)
                elif args.command == 'events':
                    value = {'events': store.events(args.after, args.limit)}
                elif args.command == 'declare-comparison':
                    value = declare(store, args.protocol)
                elif args.command == 'compare':
                    value = comparison_report(store, args.destination)
                elif args.command == 'pause-dispatch':
                    value = pause(store, args.reason)
                elif args.command == 'unpause-dispatch':
                    value = unpause(store)
                elif args.command == 'maintenance-status':
                    value = store.maintenance()
                elif args.command == 'backup':
                    value = backup(store, args.destination, args.max_bytes)
                else:
                    value = report(store, args.destination)
        print(canonical(value).decode())
        if args.command in ['run', 'continue'] and not args.once and value['status'] != 'completed':
            return 1
        if args.command == 'dashboard' and value['checkpoint_errors']:
            return 1  # Stopped, but a workspace kept WAL pages or could not be checked.
        return 0
    except (Error, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(canonical({'error': {'code': getattr(exc, 'code', 'campaign_error'), 'message': str(exc)}}).decode(), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # Decisions are transactional. A launch the interrupt cut short is
        # recorded as uncertain; continue observes issued jobs and never
        # submits them again.
        print(canonical({'error': {'code': 'interrupted', 'message': 'interrupted; continue observes issued jobs'}}).decode(),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
