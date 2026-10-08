import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.character_chat.group_upgrade import upgrade_session
from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.runtime import validate_supported_session


class GroupUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.repo = CharacterSessionRepository(self.directory,
            validator=validate_supported_session, supported_schemas=(1, 2))
        self.session = self.repo.create(create_session(str(uuid4()),
            {'name': '合成角色', 'description': '仅测试'},
            {'kind': 'character', 'key': '合成角色'}))
        self.sid = self.session['session_id']
        self.path = self.directory / f'{self.sid}.json'
        # Original formatting must survive in the backup, not just JSON values.
        self.path.write_text(json.dumps(self.session, ensure_ascii=False, indent=3), encoding='utf-8')
        self.raw = self.path.read_bytes()
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def upgrade(self, **changes):
        args = dict(expected_revision=0, expected_sha256=self.digest)
        args.update(changes)
        return upgrade_session(self.repo, self.sid, **args)

    def backups(self):
        return list((self.directory / '.upgrade-backups').glob('*.bak'))

    def assert_code(self, code, operation):
        with self.assertRaises(CharacterSessionError) as caught:
            operation()
        self.assertEqual(code, caught.exception.code)

    def test_exact_private_backup_and_idempotent_repeat(self):
        result = self.upgrade()
        self.assertTrue(result['changed'])
        self.assertEqual(self.digest, result['original_sha256'])
        self.assertEqual(self.raw, self.backups()[0].read_bytes())
        self.assertEqual([self.sid], self.repo.session_ids())
        self.assertEqual(2, self.repo.load(self.sid)['schema_version'])
        new_raw = self.path.read_bytes()
        self.assertFalse(self.upgrade()['changed'])
        self.assertEqual(new_raw, self.path.read_bytes())
        self.assertEqual(1, len(self.backups()))
        old = CharacterSessionRepository(self.directory)
        self.assert_code('SCHEMA_READ_ONLY', lambda: old.transaction(self.sid, lambda _: (None, True)))
        self.assertEqual(new_raw, self.path.read_bytes())

    def test_revision_hash_and_input_guards_do_not_backup(self):
        for changes, code in [({'expected_revision': True}, 'INVALID_REQUEST'),
                              ({'expected_sha256': 'wrong'}, 'INVALID_REQUEST'),
                              ({'expected_revision': 1}, 'REVISION_CONFLICT'),
                              ({'expected_sha256': '0' * 64}, 'REVISION_CONFLICT')]:
            with self.subTest(changes=changes):
                self.assert_code(code, lambda: self.upgrade(**changes))
        self.assertEqual([], self.backups())
        self.assertEqual(self.raw, self.path.read_bytes())

    def test_backup_fsync_failure_never_replaces_original(self):
        with patch('core.character_chat.group_upgrade.os.fsync', side_effect=OSError('test')):
            self.assert_code('BACKUP_FAILED', self.upgrade)
        self.assertEqual(self.raw, self.path.read_bytes())
        self.assertEqual([], self.backups())

    def test_conversion_failure_retains_exact_backup_and_original(self):
        with patch('core.character_chat.group_upgrade.convert_legacy_session',
                   side_effect=CharacterSessionError('SESSION_LIMIT')):
            self.assert_code('SESSION_LIMIT', self.upgrade)
        self.assertEqual(self.raw, self.path.read_bytes())
        self.assertEqual(self.raw, self.backups()[0].read_bytes())

    def test_atomic_replace_failure_retains_original_and_backup(self):
        with patch('core.character_chat.repository.os.replace', side_effect=OSError('test')):
            self.assert_code('PERSISTENCE_FAILED', self.upgrade)
        self.assertEqual(self.raw, self.path.read_bytes())
        self.assertEqual(self.raw, self.backups()[0].read_bytes())
        self.assertEqual([], list(self.directory.glob('.character-*.tmp')))
        # Retrying makes a second unique backup, never overwrites the first.
        self.assertTrue(self.upgrade()['changed'])
        self.assertEqual(2, len(self.backups()))
        self.assertTrue(all(p.read_bytes() == self.raw for p in self.backups()))

    def test_replacement_fsync_failure_retains_original(self):
        calls = 0
        real_fsync = __import__('os').fsync
        def fsync(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('temporary fsync failure')
            real_fsync(fd)
        with patch('core.character_chat.repository.os.fsync', side_effect=fsync):
            self.assert_code('PERSISTENCE_FAILED', self.upgrade)
        self.assertEqual(self.raw, self.path.read_bytes())
        self.assertEqual(self.raw, self.backups()[0].read_bytes())

    def test_external_edit_before_replace_is_not_overwritten(self):
        from core.character_chat.group_migration import convert_legacy_session
        altered = self.raw + b'\n'
        def convert(original):
            self.path.write_bytes(altered)
            return convert_legacy_session(original)
        with patch('core.character_chat.group_upgrade.convert_legacy_session', side_effect=convert):
            self.assert_code('REVISION_CONFLICT', self.upgrade)
        self.assertEqual(altered, self.path.read_bytes())
        self.assertEqual(self.raw, self.backups()[0].read_bytes())

    def test_unsupported_and_deleted_never_backup(self):
        old = CharacterSessionRepository(self.directory)
        self.assert_code('SCHEMA_READ_ONLY', lambda: upgrade_session(old, self.sid,
            expected_revision=0, expected_sha256=self.digest))
        self.repo.delete(self.sid, expected_revision=0)
        self.assert_code('SESSION_DELETED', self.upgrade)
        self.assertEqual([], self.backups())

    def test_existing_backup_is_never_overwritten_or_removed(self):
        fixed = uuid4()
        directory = self.directory / '.upgrade-backups'
        directory.mkdir()
        backup = directory / f'{self.sid}.{self.digest}.{fixed}.schema1.bak'
        backup.write_bytes(b'previous private backup')
        with patch('core.character_chat.group_upgrade.uuid4', return_value=fixed):
            self.assert_code('BACKUP_FAILED', self.upgrade)
        self.assertEqual(b'previous private backup', backup.read_bytes())
        self.assertEqual(self.raw, self.path.read_bytes())

    def test_pending_worker_blocks_upgrade_without_backup(self):
        from core.character_chat.service import CharacterChatService
        from tests.test_character_chat_lifecycle import FakeTransport
        service = CharacterChatService(self.repo, FakeTransport())
        begun = service.begin(self.sid, {'client_action_id': str(uuid4()),
            'expected_revision': 0, 'operation': 'send', 'content': '还在生成'})
        raw = self.path.read_bytes()
        self.assert_code('SESSION_BUSY', lambda: self.upgrade(
            expected_sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(raw, self.path.read_bytes())
        self.assertEqual([], self.backups())
        service.cancel(self.sid, begun['job']['request_id'])

    def test_unsafe_backup_directory_and_unknown_schema_do_not_write(self):
        # A file occupying the directory also fails closed, without deletion.
        directory = self.directory / '.upgrade-backups'
        directory.write_bytes(b'not a directory')
        self.assert_code('BACKUP_FAILED', self.upgrade)
        self.assertEqual(b'not a directory', directory.read_bytes())
        future = dict(self.session, schema_version=3)
        self.path.write_text(json.dumps(future), encoding='utf-8')
        raw = self.path.read_bytes()
        self.assert_code('SCHEMA_READ_ONLY', lambda: self.upgrade(
            expected_sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(raw, self.path.read_bytes())


if __name__ == '__main__':
    unittest.main()
