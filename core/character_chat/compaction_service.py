"""One authorized background summary per normal completed reply, never on GET."""
import asyncio
import json

from core.prompt_studio import compose_prompt, plan_model_request, RequestMessagePart
from core.request_budget import budget_report
from . import compaction
from .models import CharacterSessionError


class CharacterCompactionService:
    def __init__(self, owner):
        self.owner = owner
        self.workers = {}

    def schedule(self, sid, *, explicit=False):
        if self.owner.closed or sid in self.workers:
            return
        job = compaction.prepare(self.owner.repository.load(sid), explicit=explicit)
        if job:
            self.workers[sid] = asyncio.create_task(self._run(sid, job))

    async def close(self):
        tasks = list(self.workers.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, sid, job):
        try:
            async with self.owner.slots:
                if not compaction.current_job(self.owner.repository.load(sid), job):
                    return
                config = self.owner.transport.snapshot()
                system = compose_prompt('character.compaction.v1', {})
                plan = plan_model_request(system, [RequestMessagePart('character.compaction.messages',
                    json.dumps({'messages': job['messages']}, ensure_ascii=False))],
                    temperature=0.2, max_tokens=2048, trace_label='character.compaction', mode='json',
                    contract_id='character.compaction.v1', context_contract_id='character.compaction.input.v1')
                report = budget_report(plan.system_prompt, plan.user_prompt, output_tokens=2048,
                                       options=config.get('budget_options'), manifest=plan.prompt_manifest)
                if not report['fits']:
                    raise CharacterSessionError('CONTEXT_LIMIT')
                raw = await self.owner.transport.generate_summary(config, plan, report)
                summary = compaction.parse_summary(raw)
                self.owner._transaction(sid, lambda s: compaction.commit(s, job, summary))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            code = getattr(exc, 'code', 'PROVIDER_FAILED')
            try:
                self.owner._transaction(sid, lambda s: compaction.failed(s, job, code))
            except CharacterSessionError:
                pass  # Deleted sessions must not be recreated by a late result.
        finally:
            self.workers.pop(sid, None)
