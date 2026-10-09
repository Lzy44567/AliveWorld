import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1 import character_chat_routes as routes
from api.v1.character_group_http import GroupSubscription, display_mode
from core.character_chat.runtime import CharacterRuntime, runtime_lifespan
from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.group_creation import create_group_session
from tests.test_character_group_service import FakeGroupTransport
from tests.test_character_chat_lifecycle import FakeTransport


class GroupRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.transport = FakeGroupTransport()
        self.runtime = CharacterRuntime(Path(self.temp.name), transport=self.transport)
        app = FastAPI(lifespan=runtime_lifespan(lambda: self.runtime)); app.include_router(routes.router)
        self.asset = patch.object(routes, 'load_asset', return_value={'name': '合成', 'description': '固定', '_external_import': {'private': 'hidden'}})
        self.mock_asset = self.asset.start(); self.addCleanup(self.asset.stop)
        self.client = TestClient(app); self.client.__enter__(); self.addCleanup(self.client.__exit__, None, None, None)
        self.prefix = '/api/v1/character-sessions'
        self.creation = {'client_creation_id': str(uuid4()), 'ai_asset_ref': {'kind': 'character', 'key': '合成'},
                         'presentation_mode': 'messenger', 'schema_version': 2}
        response = self.client.post(self.prefix, json=self.creation)
        self.assertEqual(201, response.status_code, response.text)
        self.sid = response.json()['session_id']; self.url = self.prefix + '/' + self.sid

    def send(self, content='输入', **changes):
        revision = self.client.get(self.url).json()['revision']
        payload = {'client_action_id': str(uuid4()), 'expected_revision': revision, 'operation': 'send', 'content': content, **changes}
        return self.client.post(self.url + '/actions', json=payload), payload

    def idle(self):
        self.client.portal.call(self.runtime.groups.wait_idle, self.sid)

    def test_explicit_creation_and_idempotent_format_identity(self):
        self.mock_asset.reset_mock()
        self.assertEqual(201, self.client.post(self.prefix, json=self.creation).status_code)
        self.mock_asset.assert_not_called()
        self.assertEqual(409, self.client.post(self.prefix, json={**self.creation, 'schema_version': 1}).status_code)
        stored = self.runtime.repository.load(self.sid)
        self.assertEqual(2, stored['schema_version']); self.assertNotIn('turns', stored)
        self.assertEqual([], stored['inputs']); self.assertEqual([], stored['groups'])
        self.assertNotIn('hidden', self.client.get(self.url).text)

    def test_contact_settings_quota_and_edit_activity_without_paid_call(self):
        value = self.client.get(self.url + '/proactive').json()
        self.assertFalse(value['settings']['enabled'])
        response = self.client.put(self.url + '/proactive', json={
            'expected_revision': value['revision'], 'settings': {'enabled': True, 'idle_seconds': 60}})
        self.assertEqual(200, response.status_code, response.text)
        self.assertTrue(response.json()['settings']['enabled'])
        activity = self.client.post(self.url + '/activity', json={'client_id': str(uuid4())})
        self.assertEqual(200, activity.status_code, activity.text)
        self.assertEqual('idle', activity.json()['state'])
        quota = self.client.put(self.prefix + '/contact-quota', json={'call_limit': 2, 'contact_limit': 3})
        self.assertEqual(200, quota.status_code, quota.text)
        self.assertEqual(2, self.client.get(self.prefix + '/contact-quota').json()['call_limit'])
        self.assertEqual([], self.transport.calls)
        self.assertNotIn('plan', self.client.get(self.url).json().get('proactive', {}))

    def test_contact_does_not_upgrade_or_authorize_legacy_session(self):
        response = self.client.post(self.prefix, json={**self.creation,
            'client_creation_id': str(uuid4()), 'schema_version': 1})
        old = response.json(); url = self.prefix + '/' + old['session_id']
        self.assertFalse(self.client.get(url + '/proactive').json()['supported'])
        denied = self.client.put(url + '/proactive', json={
            'expected_revision': old['revision'], 'settings': {'enabled': True}})
        self.assertEqual(409, denied.status_code)
        self.assertEqual(old, self.client.get(url).json())

    def test_contact_batch_static_route_and_quiet_hours(self):
        before = self.client.get(self.url).json()['revision']
        result = self.client.put(self.prefix+'/contact-batch',json={'enabled':True,'targets':[{'session_id':self.sid,'expected_revision':before}]})
        self.assertEqual(200,result.status_code,result.text)
        self.assertTrue(result.json()['results'][0]['ok'])
        revision = self.client.get(self.url).json()['revision']
        quiet = {'enabled':True,'start':'22:00','end':'08:00'}
        response = self.client.put(self.url+'/proactive',json={'expected_revision':revision,'settings':{'quiet_hours':quiet}})
        self.assertEqual(200,response.status_code,response.text)
        self.assertEqual(quiet,response.json()['settings']['quiet_hours'])
        stale = self.client.put(self.prefix+'/contact-batch',json={'enabled':False,'targets':[{'session_id':self.sid,'expected_revision':before}]})
        self.assertEqual('REVISION_CONFLICT',stale.json()['results'][0]['code'])

    def test_each_display_returns_fast_json_while_provider_waits_and_replays_once(self):
        for mode in ('stream', 'gaps', 'instant'):
            self.client.portal.call(self.transport.gate.clear)
            response, payload = self.send(display_mode=mode)
            self.assertEqual(202, response.status_code, response.text)
            self.assertIn('application/json', response.headers['content-type'])
            replay = self.client.post(self.url + '/actions', json=payload)
            self.assertIn(replay.status_code, (200, 202))
            self.client.portal.call(self.transport.gate.set); self.idle()
        self.assertEqual(3, len(self.transport.calls))
        value = self.client.get(self.url).json()
        self.assertEqual(9, len(value['messages'])); self.assertNotIn('turns', value)
        self.assertEqual(6, value['unread_count'])

    def test_display_contract_and_wrong_schema_fields_are_rejected(self):
        for changes in ({'display_mode': []}, {'display_mode': None}, {'delivery': None}, {'display_mode': 'gaps', 'delivery': 'stream'},
                        {'display_mode': 'stream', 'delivery': 'non_stream'}, {'target_turn_id': str(uuid4())}):
            response, _ = self.send(**changes)
            self.assertEqual(400, response.status_code, response.text)
        self.assertEqual([], self.transport.calls)
        self.assertEqual(409, self.client.get(self.url + '/turns').status_code)

    def test_read_is_monotone_and_get_list_do_not_mark_or_rewrite(self):
        self.send(display_mode='instant'); self.idle()
        path = Path(self.temp.name) / f'{self.sid}.json'; before = path.read_bytes()
        value = self.client.get(self.url).json(); self.client.get(self.prefix + '?view=summary')
        self.assertEqual(before, path.read_bytes())
        seq = value['messages'][-1]['message']['seq']
        for bad in (True, -1, seq + 1, 9007199254740992):
            self.assertEqual(400, self.client.put(self.url + '/read', json={'seq': bad}).status_code)
        acknowledged = self.client.put(self.url + '/read', json={'seq': seq}).json()
        stale = self.client.put(self.url + '/read', json={'seq': 0}).json()
        self.assertEqual(acknowledged, stale); self.assertEqual(0, stale['unread_count'])

    def test_batch_pagination_undo_delete_and_auxiliary_dispatch(self):
        self.send(display_mode='instant'); self.idle()
        page = self.client.get(self.url + '/groups?limit=1').json()
        self.assertEqual(1, len(page['groups'])); self.assertEqual(3, len(page['messages']))
        self.assertEqual(200, self.client.get(self.url + '/capacity').status_code)
        self.assertEqual(200, self.client.get(self.url + '/memory/cognition').status_code)
        value = self.client.get(self.url).json()
        updated = self.client.patch(self.url, json={'expected_revision': value['revision'], 'title': '新标题'}).json()
        gid = page['groups'][0]['group_id']
        result = self.client.post(self.url + '/actions', json={'client_action_id': str(uuid4()),
            'expected_revision': updated['revision'], 'operation': 'undo', 'target_group_id': gid})
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual(409, self.client.get(self.url + '/groups?before=' + gid).status_code)
        revision = self.client.get(self.url).json()['revision']
        self.assertEqual(204, self.client.request('DELETE', self.url, json={'expected_revision': revision}).status_code)
        self.assertEqual(204, self.client.request('DELETE', self.url, json={'expected_revision': revision}).status_code)

    def test_old_default_creation_uses_same_runtime_but_preserves_protocol_and_file(self):
        old_payload = {**self.creation, 'client_creation_id': str(uuid4())}; del old_payload['schema_version']
        response = self.client.post(self.prefix, json=old_payload)
        sid = response.json()['session_id']; url = self.prefix + '/' + sid
        old = FakeTransport(); self.runtime.legacy.transport = old
        self.assertEqual(1, self.runtime.repository.load(sid)['schema_version'])
        result = self.client.post(url + '/actions', json={'client_action_id': str(uuid4()),
            'expected_revision': 0, 'operation': 'send', 'content': '旧输入', 'delivery': 'non_stream'})
        self.assertEqual(200, result.status_code, result.text)
        self.assertIn('turn', result.json()); self.assertEqual(1, old.calls)
        path = Path(self.temp.name) / f'{sid}.json'; before = path.read_bytes()
        self.client.get(url); self.client.get(self.prefix)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(400, self.client.post(url + '/actions', json={'client_action_id': str(uuid4()),
            'expected_revision': 1, 'operation': 'send', 'content': '不接受', 'display_mode': 'stream'}).status_code)

    def test_failed_retry_route_is_idempotent_and_new_inputs_resolve_to_owner(self):
        self.transport.fail = True
        response, payload = self.send(display_mode='instant'); self.idle()
        aid = payload['client_action_id']
        status = self.client.get(self.url + '/actions/' + aid).json()
        self.assertEqual('failed', status['status']); self.assertTrue(status['retryable'])
        self.transport.fail = False
        retry = {'expected_revision': status['revision'], 'retry_of': status['request_id'],
                 'retry_token': str(uuid4()), 'display_mode': 'instant'}
        url = self.url + '/actions/' + aid + '/retry'
        response = self.client.post(url, json=retry)
        self.assertEqual(202, response.status_code, response.text)
        self.idle(); calls = len(self.transport.calls)
        self.assertEqual(200, self.client.post(url, json=retry).status_code)
        self.assertEqual(calls, len(self.transport.calls))
        old = self.client.get(self.url + '/actions/' + aid + '?request_id=' + retry['retry_of']).json()
        self.assertEqual('failed', old['status'])
        self.client.portal.call(self.transport.gate.clear)
        self.send('第一')
        self.client.portal.call(self.transport.started.wait)
        _, child = self.send('后续')
        self.client.portal.call(self.transport.gate.set); self.idle()
        child_status = self.client.get(self.url + '/actions/' + child['client_action_id']).json()
        self.assertEqual('committed', child_status['status']); self.assertIn('request_id', child_status)

    def test_multiworker_blocks_c4_writes_and_subscription_not_reads(self):
        self.runtime.workers = '2'
        response, _ = self.send()
        self.assertEqual(503, response.status_code)
        self.assertEqual(503, self.client.get(self.url + '/events').status_code)
        self.assertEqual(200, self.client.get(self.url).status_code)
        self.assertEqual([], self.transport.calls)

    def test_main_factory_uses_injected_runtime_lifespan(self):
        from main import create_app
        with tempfile.TemporaryDirectory() as directory:
            runtime = CharacterRuntime(Path(directory), transport=FakeGroupTransport())
            app = create_app(frontend_dist=Path(directory) / 'empty', character_runtime_factory=lambda: runtime)
            with TestClient(app) as client:
                self.assertEqual(200, client.get('/api/health').status_code)
                created = client.post(self.prefix, json={**self.creation, 'client_creation_id': str(uuid4())})
                self.assertEqual(201, created.status_code, created.text)
                self.assertTrue(runtime.started)
            self.assertTrue(runtime.closed)


class SubscriptionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.transport = FakeGroupTransport(); self.transport.gate.clear()
        self.runtime = CharacterRuntime(Path(self.temp.name), transport=self.transport)
        await self.runtime.start(); self.addAsyncCleanup(self.runtime.close)
        value = create_group_session(str(uuid4()), {'name': '合成', 'description': '固定'}, {'kind': 'character', 'key': '合成'})
        self.runtime.repository.create(value); self.sid = value['session_id']

    async def send(self):
        await self.runtime.groups.send(self.sid, {'client_action_id': str(uuid4()), 'expected_revision': 0, 'content': '输入'})
        await asyncio.wait_for(self.transport.started.wait(), 2)

    async def test_ready_realtime_identity_disconnect_does_not_cancel(self):
        subscriber = GroupSubscription(self.runtime.groups, self.sid)
        self.addCleanup(subscriber.close)
        await self.send()
        frames = []
        while not subscriber.queue.empty():
            frame, _ = subscriber.queue.get_nowait(); frames.append(frame)
        data = [json.loads(frame.split('data: ', 1)[1]) for frame in frames]
        self.assertTrue(frames[0].startswith('event: ready'))
        self.assertEqual(list(range(1, len(data) + 1)), [d['event_seq'] for d in data])
        for record in data[2:]:
            self.assertIn('action_id', record); self.assertIn('request_id', record); self.assertIn('group_id', record)
        self.assertEqual(2, sum(f.startswith('event: preview_start') for f in frames))
        subscriber.close(); self.transport.gate.set()
        await self.runtime.groups.wait_idle(self.sid)
        self.assertEqual(3, len(self.runtime.groups.view(self.sid)['messages']))
        self.assertEqual(1, len(self.transport.calls))

    async def test_frame_and_byte_overflow_only_detach(self):
        for use_bytes in (False, True):
            subscriber = GroupSubscription(self.runtime.groups, self.sid)
            for _ in range(66):
                subscriber.emit('preview_delta', {'text': 'x' * (262144 if use_bytes else 1)})
            self.assertTrue(subscriber.closed); self.assertEqual(0, subscriber.bytes)
            self.assertNotIn(subscriber.emit, self.runtime.groups.subscribers[self.sid])
        await self.send(); self.transport.gate.set(); await self.runtime.groups.wait_idle(self.sid)
        self.assertEqual(2, self.runtime.groups.view(self.sid)['unread_count'])

    async def test_late_subscription_has_ready_not_private_or_preview_replay(self):
        await self.send()
        subscriber = GroupSubscription(self.runtime.groups, self.sid); self.addCleanup(subscriber.close)
        self.assertEqual(1, subscriber.queue.qsize())
        frame, _ = subscriber.queue.get_nowait()
        self.assertTrue(frame.startswith('event: ready')); self.assertNotIn('preview', frame)
        self.transport.gate.set(); await self.runtime.groups.wait_idle(self.sid)
        frames = []
        while not subscriber.queue.empty():
            frames.append(subscriber.queue.get_nowait()[0])
        body = ''.join(frames)
        for forbidden in ('ledger_plan', 'ledger_inverse', 'candidates', 'profile_snapshot', 'user_prompt'):
            self.assertNotIn(forbidden, body)
        self.assertIn('event: group_saved', body)

    async def test_no_lifespan_c4_creation_is_unavailable_not_lazy(self):
        app = FastAPI(); app.include_router(routes.router)
        with TestClient(app) as client:
            response = client.post('/api/v1/character-sessions', json={'client_creation_id': str(uuid4()),
                'ai_asset_ref': {'kind': 'character', 'key': '未读取'}, 'presentation_mode': 'messenger', 'schema_version': 2})
        self.assertEqual(503, response.status_code)

    async def test_actual_asgi_subscription_disconnect_keeps_worker_running(self):
        app = FastAPI(); app.state.character_runtime = self.runtime; app.include_router(routes.router)
        path = '/api/v1/character-sessions/' + self.sid + '/events'
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'}, 'http_version': '1.1',
                 'method': 'GET', 'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': b'',
                 'root_path': '', 'headers': [], 'client': ('test', 1), 'server': ('test', 80)}
        disconnected = asyncio.Event(); ready = asyncio.Event(); first = True; frames = []
        async def receive():
            nonlocal first
            if first:
                first = False
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            await disconnected.wait()
            return {'type': 'http.disconnect'}
        async def send(message):
            frames.append(message)
            if b'event: ready' in message.get('body', b''):
                ready.set()
        task = asyncio.create_task(app(scope, receive, send))
        try:
            await asyncio.wait_for(ready.wait(), 10)
            await self.send()
            await asyncio.sleep(.01)
            disconnected.set()
            await asyncio.wait_for(task, 10)
            self.assertFalse(self.runtime.groups.workers[self.sid].done())
            self.assertEqual(set(), self.runtime.groups.subscribers[self.sid])
            self.transport.gate.set(); await self.runtime.groups.wait_idle(self.sid)
            self.assertEqual(2, self.runtime.groups.view(self.sid)['unread_count'])
            self.assertEqual(1, len(self.transport.calls))
            self.assertEqual(200, frames[0]['status'])
            self.assertIn(b'event: accepted', b''.join(f.get('body', b'') for f in frames))
        finally:
            if not task.done():
                task.cancel(); await asyncio.gather(task, return_exceptions=True)


class DisplayTests(unittest.TestCase):
    def test_mapping_and_conflict(self):
        self.assertEqual('stream', display_mode({}))
        self.assertEqual('instant', display_mode({'delivery': 'non_stream'}))
        self.assertEqual('gaps', display_mode({'display_mode': 'gaps', 'delivery': 'non_stream'}))
        with self.assertRaises(CharacterSessionError):
            display_mode({'display_mode': 'gaps', 'delivery': 'stream'})
