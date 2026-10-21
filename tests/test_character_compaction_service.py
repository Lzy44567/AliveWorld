import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from core.character_chat.group_service import CharacterGroupService
from core.character_chat.group_schema import validate_schema2
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat import compaction as c
from tests.test_character_compaction import conversation
from tests.test_character_group_service import FakeGroupTransport


class SummaryTransport(FakeGroupTransport):
    def __init__(self):
        super().__init__()
        self.summaries = []
        self.summary_gate = asyncio.Event()
        self.summary_gate.set()

    async def generate_summary(self, config, plan, report):
        self.summaries.append(json.loads(plan.user_prompt))
        await self.summary_gate.wait()
        return '{"summary":"共同经历已整理"}'


class CompactionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = CharacterSessionRepository(Path(self.temp.name), validator=validate_schema2, supported_schemas=(2,))
        # Import the synthetic completed fixture, preserving its domain revision.
        value = conversation()
        self.repo._write(value)
        self.sid = value['session_id']
        self.transport = SummaryTransport()
        self.service = CharacterGroupService(self.repo, self.transport)
        self.addAsyncCleanup(self.service.close)

    async def send(self):
        await self.service.send(self.sid, {'client_action_id': str(uuid4()),
            'expected_revision': self.repo.load(self.sid)['revision'], 'content': '继续'}, 'instant')
        await self.service.wait_idle(self.sid)
        if task := self.service.compaction.workers.get(self.sid):
            await task

    async def test_get_start_enable_zero_calls_normal_reply_one(self):
        await self.service.start()
        self.service.view(self.sid)
        await self.send()
        self.assertEqual([], self.transport.summaries)
        self.service.long_chat_update(self.sid, self.repo.load(self.sid)['revision'], True, True)
        self.assertEqual([], self.transport.summaries)
        await self.send()
        self.assertEqual(1, len(self.transport.summaries))
        self.assertEqual(1, len(c.references(self.repo.load(self.sid))))
        await self.send()
        self.assertEqual(1, len(self.transport.summaries))
        self.assertIn('derived_summaries', self.transport.calls[-1]['data'])

    async def test_disable_cancels_late_summary(self):
        self.transport.summary_gate.clear()
        self.service.long_chat_update(self.sid, self.repo.load(self.sid)['revision'], True, True, True)
        await asyncio.sleep(.02)
        self.assertEqual(1, len(self.transport.summaries))
        self.service.long_chat_update(self.sid, self.repo.load(self.sid)['revision'], False)
        self.transport.summary_gate.set()
        await asyncio.sleep(.02)
        self.assertEqual([], c.state(self.repo.load(self.sid))['segments'])
