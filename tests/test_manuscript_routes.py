import json
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.manuscript_project import ManuscriptProjects
from api.v1 import manuscript_routes as routes


class Engine:
    def __init__(self):
        self.calls = []
        self.error = None

    def chat_json(self, system, user, **kwargs):
        self.calls.append(json.loads(user))
        return json.dumps({'candidates': [{'kind':'future_notes', 'name':'未来',
            'origin':'original', 'source_quote':'将来觉醒', 'content':{'text':'将来觉醒'}}],
            'notes':'尚未发生'}), self.error


class ManuscriptRouteTests(unittest.TestCase):
    def test_explicit_selection_cost_failure_reload_and_no_publication(self):
        with tempfile.TemporaryDirectory() as root:
            repo = ManuscriptProjects(root)
            engine = Engine()
            app = FastAPI(); app.include_router(routes.router, prefix='/manuscripts')
            with patch.object(routes, 'projects', repo), patch.object(routes, 'get_task_engine', return_value=engine):
                client = TestClient(app)
                project = client.post('/manuscripts', json={'title':'试稿', 'source_text':'不发送的私人段落。将来觉醒'}).json()
                url = '/manuscripts/' + project['id']
                body = {'expected_revision':0, 'selected_text':'将来觉醒', 'acknowledged':False}
                self.assertEqual(400, client.post(url+'/analyze', json=body).status_code)
                self.assertFalse(engine.calls)
                body['acknowledged'] = True
                response = client.post(url+'/analyze', json=body)
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual('将来觉醒', engine.calls[0]['manuscript'])
                self.assertNotIn('私人', json.dumps(engine.calls, ensure_ascii=False))
                self.assertEqual('pending', response.json()['candidates'][0]['status'])
                self.assertEqual(409, client.post(url+'/analyze', json=body).status_code)
                self.assertEqual(1, len(engine.calls))
                engine.error = 'synthetic timeout'
                body['expected_revision'] = 1
                self.assertEqual(400, client.post(url+'/analyze', json=body).status_code)
                self.assertEqual(response.json(), client.get(url).json())
                self.assertEqual(1, len(client.get('/manuscripts').json()['projects']))
