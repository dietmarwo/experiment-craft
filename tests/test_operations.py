"""Offline deployment, WAL snapshots, archive boundaries and dispatch gates."""
import copy
from contextlib import closing
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import jsonschema

from experiment_craft.campaign import drive
from experiment_craft.comparison import bound_protocol, declare
from experiment_craft.deployment import export, load, plan, select
from experiment_craft.manifest import compile_manifest
from experiment_craft.operations import audit, backup, pause, restore
from experiment_craft.runtime import Runtime
from experiment_craft.storage import Error, Store, canonical, identity, read_json, write_json
from test_campaign import campaign
from test_comparison import fcmaes, protocol, state_for

PROJECT = Path(__file__).resolve().parents[1]


class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        path = self.base / 'source.json'
        write_json(path, campaign([{'id': 'a', 'job': fcmaes()}, {'id': 'b', 'job': fcmaes(population=32)}]))
        self.compiled = compile_manifest(path)
        self.root = self.base / 'campaign'
        self.root.mkdir()
        self.store = Store(self.root, create=True)
        with self.store.edit({'event': 'test_fixture'}) as current:
            current.update(state_for(self.compiled))
        write_json(self.root / 'plan.json', self.store.read()['plan'])
        self.archive = self.base / 'backup.zip'

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def make_backup(self):
        pause(self.store)
        return backup(self.store, self.archive)

    def error(self, code, call):
        with self.assertRaises(Error) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def rewrite(self, change=None, extra=None, symlink=None, duplicate=False):
        target = self.base / 'changed.zip'
        with zipfile.ZipFile(self.archive) as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        if change:
            change(members)
        with zipfile.ZipFile(target, 'w') as output:
            for name, content in members.items():
                if name == symlink:
                    info = zipfile.ZipInfo(name)
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    output.writestr(info, content)
                else:
                    output.writestr(name, content)
            if extra:
                output.writestr(extra, b'outside')
            if duplicate:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    output.writestr('BACKUP.json', members['BACKUP.json'])
        return target

    def test_a_decision_committed_during_backup_refuses_the_archive(self):
        import experiment_craft.operations as module
        from experiment_craft.campaign import request_stop
        pause(self.store)
        original = module.audit
        def stopping(store):
            with closing(Store(self.root)) as other:
                request_stop(other)
            return original(store)
        with patch.object(module, 'audit', stopping):
            self.error('backup_changed', lambda: backup(self.store, self.archive))
        self.assertFalse(self.archive.exists())
        self.assertEqual([p.name for p in self.base.iterdir() if p.name.startswith('.backup-')], [])
        backup(self.store, self.archive)
        with zipfile.ZipFile(self.archive) as archive:
            (self.base / 'check').mkdir()
            (self.base / 'check' / 'campaign.sqlite3').write_bytes(archive.read('data/campaign.sqlite3'))
        with closing(Store(self.base / 'check')) as copy_:
            self.assertTrue(copy_.read()['stop_requested'])

    def test_refused_backups_and_restores_leave_nothing_behind(self):
        self.error('dispatch_not_paused', lambda: backup(self.store, self.base / 'new' / 'dir' / 'backup.zip'))
        self.assertFalse((self.base / 'new').exists())
        self.error('invalid_backup', lambda: restore(self.base / 'absent.zip', self.base / 'restored'))
        self.error('invalid_backup', lambda: restore(self.base, self.base / 'restored'))

    def test_pause_is_a_separate_versioned_control_and_does_not_contact_runtime(self):
        before = self.store.read()
        self.assertFalse(self.store.maintenance()['paused'])
        with patch.object(Runtime, 'call', side_effect=AssertionError('pause contacted runtime')):
            first = pause(self.store, 'backup')
            second = pause(self.store, 'new operator pause')
        self.assertEqual(self.store.read(), before)
        self.assertTrue(first['paused'])
        self.assertEqual(second['generation'], first['generation'] + 1)
        self.error('dispatch_paused', lambda: drive(self.store))

    def test_pause_can_commit_while_another_client_holds_the_advancement_lock(self):
        with self.store.advance_lock(), closing(Store(self.root)) as other:
            self.assertTrue(pause(other)['paused'])
            self.error('campaign_busy', lambda: backup(other, self.archive))

    def test_malformed_maintenance_is_refused_instead_of_returning_an_invalid_status(self):
        value = pause(self.store)
        value['reason'] = {'invalid': 'reason'}
        self.store.db.execute('UPDATE maintenance SET value=?', (canonical(value).decode(),))
        self.error('invalid_maintenance', self.store.maintenance)

    def test_database_permissions_and_private_archive_mode_are_preserved(self):
        (self.root / 'campaign.sqlite3').chmod(0o600)
        self.make_backup()
        self.assertEqual(stat.S_IMODE(self.archive.stat().st_mode), 0o600)
        restore(self.archive, self.base / 'restored')
        self.assertEqual(stat.S_IMODE((self.base / 'restored/campaign.sqlite3').stat().st_mode), 0o600)

    def test_backup_requires_pause_and_never_clobbers(self):
        self.error('dispatch_not_paused', lambda: backup(self.store, self.archive))
        self.assertFalse(self.archive.exists())
        first = self.make_backup()
        original = self.archive.read_bytes()
        self.error('backup_exists', lambda: backup(self.store, self.archive))
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertEqual(first['sha256'], hashlib.sha256(original).hexdigest())
        self.error('invalid_backup', lambda: backup(self.store, self.root / 'backup.zip'))

    def test_wal_snapshot_includes_committed_changes_and_restore_starts_paused(self):
        self.store.db.execute('PRAGMA wal_autocheckpoint=0')
        with self.store.edit({'event': 'wal_probe'}) as state:
            state['wal_probe'] = 'committed only through SQLite'
        before = self.store.read()
        self.make_backup()
        events = self.store.events()
        with patch.object(Runtime, 'call', side_effect=AssertionError('restore contacted runtime')):
            result = restore(self.archive, self.base / 'restored')
        self.assertFalse(result['runtime_contacted'])
        with closing(Store(self.base / 'restored')) as restored:
            self.assertEqual(restored.read(), before)
            self.assertEqual(restored.events()[:-1], events)
            self.assertTrue(restored.maintenance()['paused'])
            self.assertEqual(restored.read()['steps'], self.store.read()['steps'])
            self.error('dispatch_paused', lambda: drive(restored))
        self.assertEqual(self.store.events(), events)

    def test_sealed_p6_protocol_keeps_all_three_anchors_across_restore(self):
        path = self.base / 'comparison.json'
        write_json(path, protocol(self.store.read()['plan']))
        binding = declare(self.store, path)
        self.make_backup()
        restore(self.archive, self.base / 'restored')
        with closing(Store(self.base / 'restored')) as restored:
            self.assertEqual(bound_protocol(restored), binding)
            self.assertEqual(restored.read()['comparison_binding_id'], binding['binding_id'])

    def test_authoritative_binary_bytes_and_modes_survive_but_live_cli_logs_do_not(self):
        path = self.root / 'requests/a/inputs/0'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'\0\xffbinary input')
        path.chmod(0o750)
        log = path.parents[1] / 'runner.stdout'
        log.write_text('a surviving process may still append here')
        self.make_backup()
        restore(self.archive, self.base / 'restored')
        restored = self.base / 'restored/requests/a/inputs/0'
        self.assertEqual(restored.read_bytes(), path.read_bytes())
        self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o750)
        self.assertFalse((self.base / 'restored/requests/a/runner.stdout').exists())

    def test_restore_refuses_existing_workspaces_and_leaves_source_untouched(self):
        self.make_backup()
        marker = self.base / 'existing'
        marker.mkdir()
        (marker / 'keep').write_text('keep')
        self.error('workspace_exists', lambda: restore(self.archive, marker))
        self.assertEqual((marker / 'keep').read_text(), 'keep')

    def test_zip_traversal_extra_entries_duplicates_and_symlinks_are_refused(self):
        self.make_backup()
        for kwargs in [{'extra': '../../outside'}, {'extra': 'data/unknown'}, {'duplicate': True},
                       {'symlink': 'data/plan.json'}]:
            with self.subTest(kwargs=kwargs):
                source = self.rewrite(**kwargs)
                self.error('invalid_backup', lambda: restore(source, self.base / 'rejected'))
                self.assertFalse((self.base / 'rejected').exists())
                self.assertFalse((self.base.parent / 'outside').exists())

    def test_tampered_entry_and_manifest_fail_without_publishing_a_workspace(self):
        self.make_backup()
        def data(members):
            members['data/plan.json'] += b'changed'
        # Header size changes are caught before extraction.
        self.error('backup_size_limit', lambda: restore(self.rewrite(change=data), self.base / 'bad-size'))
        def bytes_only(members):
            value = bytearray(members['data/plan.json'])
            value[0] = ord('[')
            members['data/plan.json'] = bytes(value)
        self.error('backup_integrity', lambda: restore(self.rewrite(change=bytes_only), self.base / 'bad-bytes'))
        def manifest(members):
            value = json.loads(members['BACKUP.json'])
            value['plan_id'] = '0' * 64
            members['BACKUP.json'] = canonical(value)
        self.error('backup_integrity', lambda: restore(self.rewrite(change=manifest), self.base / 'bad-manifest'))
        self.assertFalse(any(self.base.glob('bad-*')))

    def test_byte_bounds_fail_before_publication(self):
        pause(self.store)
        self.error('backup_size_limit', lambda: backup(self.store, self.archive, max_bytes=1))
        self.assertFalse(self.archive.exists())
        backup(self.store, self.archive)
        self.error('backup_size_limit', lambda: restore(self.archive, self.base / 'small', max_bytes=1))
        self.assertFalse((self.base / 'small').exists())

    def test_backup_refuses_symlinks_and_fifos_in_authoritative_files(self):
        import os
        pause(self.store)
        directory = self.root / 'files'
        directory.mkdir()
        path = directory / 'bad'
        path.symlink_to(self.base / 'source.json')
        self.error('invalid_backup', lambda: backup(self.store, self.archive))
        path.unlink()
        os.mkfifo(path)
        self.error('invalid_input', lambda: backup(self.store, self.archive))
        self.assertFalse(self.archive.exists())

    def test_declared_backup_maintenance_and_head_schemas_match_actual_data(self):
        self.make_backup()
        with zipfile.ZipFile(self.archive) as archive:
            data = json.loads(archive.read('BACKUP.json'))
        for name, value in [('campaign-backup', data), ('campaign-maintenance', self.store.maintenance()),
                            ('campaign-head', read_json(self.root / 'head.json'))]:
            schema = read_json(files('experiment_craft').joinpath('schemas/' + name + '-0.1.schema.json'))
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(schema).validate(value)

    def test_a_changed_plan_is_not_repaired_by_backup(self):
        pause(self.store)
        value = read_json(self.root / 'plan.json')
        value['name'] = 'another plan'
        write_json(self.root / 'plan.json', value)
        self.error('backup_integrity', lambda: backup(self.store, self.archive))
        self.assertFalse(self.archive.exists())

    def test_restore_refuses_a_fifo_archive_without_waiting_for_a_writer(self):
        import os
        path = self.base / 'fifo.zip'
        os.mkfifo(path)
        self.error('invalid_backup', lambda: restore(path, self.base / 'restored'))
        self.assertFalse((self.base / 'restored').exists())

    def copy_without_wal(self, name='copy'):
        """The workspace's files without campaign.sqlite3-wal and -shm, as a careless copy takes them."""
        target = self.base / name
        shutil.copytree(self.root, target, ignore=shutil.ignore_patterns('campaign.sqlite3-wal', 'campaign.sqlite3-shm'))
        return target

    def test_a_copy_without_its_wal_is_refused_instead_of_reopening_at_an_earlier_state(self):
        # While a client has the database open, its decisions are only in the
        # WAL; initialization leaves the main file checkpointed.
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        pause(self.store, 'before the copy')
        self.assertGreater((self.root / 'campaign.sqlite3-wal').stat().st_size, 0)
        copy_ = self.copy_without_wal()
        self.error('state_regressed', lambda: Store(copy_))
        with closing(Store(self.root)) as complete:
            self.assertTrue(complete.maintenance()['paused'])

    def test_an_unrecorded_decision_is_not_mistaken_for_a_regression(self):
        # A client can stop after a commit and before recording it outside SQLite.
        recorded = (self.root / 'head.json').read_bytes()
        pause(self.store)
        (self.root / 'head.json').write_bytes(recorded)
        with closing(Store(self.root)) as other:
            self.assertTrue(other.maintenance()['paused'])
            pause(other, 'again')
        last = self.store.db.execute('SELECT max(seq) FROM events').fetchone()[0]
        self.assertEqual(read_json(self.root / 'head.json')['seq'], last)

    def test_a_database_from_another_copy_is_refused(self):
        copy_ = self.base / 'copy'
        shutil.copytree(self.root, copy_)
        pause(self.store, 'original')
        with closing(Store(copy_)) as other:
            pause(other, 'copy')
        # The same decision number in a different history.
        shutil.copyfile(self.root / 'head.json', copy_ / 'head.json')
        self.error('state_regressed', lambda: Store(copy_))
        from experiment_craft.operations import check_workspace
        self.assertEqual(check_workspace(copy_)['findings'], ['head_differs'])
        for text in ['{"schema_version": "experiment.campaign.head/0.1"}', '{"seq": 1', '']:
            (copy_ / 'head.json').write_text(text)
            self.error('invalid_head', lambda: Store(copy_))
        self.assertEqual(check_workspace(copy_)['findings'], ['invalid_head'])
        (copy_ / 'head.json').unlink()
        (copy_ / 'head.json').symlink_to(self.root / 'head.json')
        self.error('invalid_head', lambda: Store(copy_))

    def test_an_unreadable_head_record_is_invalid_head(self):
        import experiment_craft.storage as module
        with patch.object(module, 'read_json', side_effect=PermissionError(13, 'Permission denied')):
            self.error('invalid_head', lambda: Store(self.root))

    def test_a_failed_head_write_does_not_fail_the_committed_decision(self):
        import experiment_craft.storage as module
        recorded = read_json(self.root / 'head.json')
        with patch.object(module.tempfile, 'mkstemp', side_effect=OSError(28, 'No space left on device')):
            self.assertTrue(pause(self.store)['paused'])
        self.assertEqual(read_json(self.root / 'head.json'), recorded)
        with closing(Store(self.root)) as other:
            self.assertTrue(other.maintenance()['paused'])
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith('.head-')], [])

    def test_the_head_record_is_as_readable_as_the_database(self):
        import os
        database = self.root / 'campaign.sqlite3'
        database.chmod(0o640)
        if os.geteuid() == 0:
            # A decision made by root, for example a sudo stop, must stay
            # readable by the workspace's owner, as SQLite's WAL does.
            os.chown(database, 65534, 65534)
        pause(self.store)
        info = (self.root / 'head.json').stat()
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o640)
        self.assertEqual((info.st_uid, info.st_gid), (database.stat().st_uid, database.stat().st_gid))

    def test_workspace_check_reads_copies_without_changing_them(self):
        from experiment_craft.operations import check_workspace
        self.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        pause(self.store)
        live = check_workspace(self.root)
        self.assertEqual(live['findings'], ['wal_required'])
        self.assertEqual((live['last_decision'], live['main_file_alone'], live['restored_from']), (2, 1, None))
        copy_ = self.copy_without_wal()
        before = {p: p.read_bytes() for p in copy_.rglob('*') if p.is_file()}
        result = check_workspace(copy_)
        self.assertEqual(result['findings'], ['database_behind_head'])
        self.assertEqual(result['head'], {'seq': 2, 'matches': False})
        self.assertEqual({p: p.read_bytes() for p in copy_.rglob('*') if p.is_file()}, before)
        # A workspace saved before it had a head record: a result was saved for
        # a step the database never issued.
        (copy_ / 'head.json').unlink()
        write_json(copy_ / 'results' / 'a' / 'native.json', {'saved': 'by a later decision'})
        result = check_workspace(copy_)
        self.assertEqual((result['findings'], result['unissued_with_results'], result['head']),
                         (['results_without_decision'], ['a'], None))
        self.store.close()
        self.store = Store(self.root)
        self.assertEqual(check_workspace(self.root)['findings'], [])
        with self.store.advance_lock():
            self.assertEqual((check_workspace(self.root)['findings'], check_workspace(self.root)['advancing']),
                             (['client_advancing'], True))
            self.error('campaign_busy', lambda: drive(self.store))
        self.assertFalse(check_workspace(self.root)['advancing'])
        # The check reads the kernel's lock table: taking the lock, even shared,
        # could make a starting client fail with campaign_busy.
        with patch('fcntl.flock', side_effect=AssertionError('the check took a lock')):
            check_workspace(self.root)
        archived = backup(self.store, self.archive)
        restored = check_workspace(restore(self.archive, self.base / 'restored')['workspace'])
        self.assertEqual((restored['findings'], restored['restored_from'], restored['head']['matches']),
                         ([], archived['backup_id'], True))

    def test_workspace_check_keeps_the_sqlite_locks_of_its_own_process(self):
        # Closing a descriptor of the database drops the POSIX locks that this
        # process holds on it; another client's close would then remove the WAL
        # that this process still writes to.
        import subprocess
        import sys
        from experiment_craft.operations import check_workspace
        other = ('import sys; sys.path.insert(0, sys.argv[1])\n'
                 'from experiment_craft.storage import Store\n'
                 'store = Store(sys.argv[2])\n'
                 'with store.edit({"event": "other_client"}) as state: state["other"] = True\n'
                 'store.close()')
        check_workspace(self.root)
        subprocess.run([sys.executable, '-c', other, str(PROJECT), str(self.root)], check=True)
        pause(self.store, 'after the other client closed')
        fresh = ('import sys; sys.path.insert(0, sys.argv[1])\n'
                 'from experiment_craft.storage import Store\n'
                 'print(Store(sys.argv[2]).maintenance()["paused"])')
        result = subprocess.run([sys.executable, '-c', fresh, str(PROJECT), str(self.root)], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'True'), result.stderr)


class Deployments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.path = self.base / 'deployment.json'
        self.value = read_json(PROJECT / 'examples/deployment/home-lab.json')
        write_json(self.path, self.value)

    def tearDown(self):
        self.tmp.cleanup()

    def rejected(self, value):
        write_json(self.path, value)
        with self.assertRaises(Error) as caught:
            load(self.path)
        self.assertEqual(caught.exception.code, 'invalid_deployment')

    def test_default_is_one_local_test_node_and_six_planned_workers_are_disabled(self):
        value = load(self.path)
        self.assertEqual(len(value['nodes']), 7)
        self.assertTrue(value['coordinator']['excluded_from_worker_pool'])
        self.assertEqual([n['id'] for n in value['nodes'] if n['enabled']], ['local-test'])
        runner, root, mode, commands = select(self.path)
        self.assertEqual(mode, 'foreground')
        self.assertFalse(commands)
        self.assertTrue(str(runner).startswith('/') and str(root).startswith('/'))
        for node in value['nodes'][1:]:
            self.assertEqual(node['declared'], {'cpu_slots': 16, 'memory_bytes': 128 * 1024 ** 3})

    def test_export_is_offline_and_uses_literal_native_fleet_arguments(self):
        with patch.object(Runtime, 'call', side_effect=AssertionError('deployment called runtime')):
            result = export(self.path, self.base / 'export')
        self.assertFalse(result['runtime_contacted'])
        value = read_json(self.base / 'export/plan.json')
        command = value['nodes'][1]['register_on_coordinator']
        self.assertEqual(command[3:7], ['fleet', 'nodes', 'add', 'worker-01'])
        self.assertIn('--known-hosts', command)
        self.assertIn('--identity-file', command)
        self.assertEqual(value['nodes'][0]['register_on_coordinator'], None)
        for name, data in [('deployment', self.value), ('deployment-plan', value)]:
            schema = read_json(PROJECT / 'experiment_craft/schemas' / (name + '-0.1.schema.json'))
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(schema).validate(data)

    def test_duplicate_names_endpoints_and_roots_are_refused(self):
        for mutate in [lambda v: v['nodes'].append(copy.deepcopy(v['nodes'][0])),
                       lambda v: v['nodes'][2].update(host=v['nodes'][1]['host']),
                       lambda v: v['nodes'][0].update(root='/srv/x/../jobs')]:
            value = copy.deepcopy(self.value)
            mutate(value)
            self.rejected(value)

    def test_the_coordinator_stays_out_of_the_worker_pool(self):
        for mutate in [lambda v: v['nodes'][1].update(host='localhost'),
                       lambda v: v['nodes'][1].update(host='127.0.0.1'),
                       lambda v: v['nodes'][1].update(host='LOCALHOST.'),
                       lambda v: v['nodes'][0].update(root=v['coordinator']['root']),
                       lambda v: v['nodes'][0].update(root=v['coordinator']['root'] + '/test'),
                       lambda v: v['nodes'][2].update(host=v['nodes'][1]['host'] + '.'),
                       lambda v: v['nodes'][2].update(id=v['nodes'][1]['id'].upper())]:
            value = copy.deepcopy(self.value)
            mutate(value)
            self.rejected(value)

    def test_ssh_identity_files_cannot_hold_ssh_expansions(self):
        for path in ['/home/research/.ssh/id_%h', '/home/research/.ssh/id_${HOME}', '/home/research/.ssh/id $x']:
            value = copy.deepcopy(self.value)
            value['nodes'][1]['identity_file'] = path
            self.rejected(value)

    def test_remote_nodes_cannot_become_the_automatic_default_or_local_campaign_target(self):
        value = copy.deepcopy(self.value)
        value['nodes'][1]['enabled'] = True
        value['default_node'] = 'worker-01'
        self.rejected(value)
        value['default_node'] = 'local-test'
        write_json(self.path, value)
        with self.assertRaises(Error) as caught:
            select(self.path, 'worker-01')
        self.assertEqual(caught.exception.code, 'unsupported_placement')

    def test_unsafe_transport_and_unknown_fields_are_not_passed_through(self):
        for mutate in [lambda v: v['nodes'][1].update(host='-oProxyCommand=bad'),
                       lambda v: v['nodes'][1].update(helper='/tmp/../helper'),
                       lambda v: v['nodes'][1].update(root='/srv/$HOME/jobs'),
                       lambda v: v['nodes'][1].update(known_hosts='/tmp/key;bad'),
                       lambda v: v.update(placement='automatic'),
                       lambda v: v['coordinator'].update(excluded_from_worker_pool=False)]:
            value = copy.deepcopy(self.value)
            mutate(value)
            self.rejected(value)

    def test_export_does_not_overwrite_an_existing_directory(self):
        target = self.base / 'exists'
        target.mkdir()
        (target / 'keep').write_text('keep')
        with self.assertRaises(Error) as caught:
            export(self.path, target)
        self.assertEqual(caught.exception.code, 'destination_exists')
        self.assertEqual((target / 'keep').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
