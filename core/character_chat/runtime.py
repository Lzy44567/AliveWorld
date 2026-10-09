"""Application-owned composition; no per-request loops or schema conversion."""
import asyncio
import os
from contextlib import asynccontextmanager

from .models import CharacterSessionError, validate_session
from .group_schema import validate_schema2
from .repository import CharacterSessionRepository
from .service import CharacterChatService
from .group_service import CharacterGroupService
from .provider_slots import ProviderSlots
from .proactive_service import ProactiveContactService


def validate_supported_session(value):
    version = value.get('schema_version')
    if type(version) is not int or version not in (1, 2):
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    (validate_session if version == 1 else validate_schema2)(value)


class CharacterRuntime:
    def __init__(self, directory, *, transport=None, preference_loader=None, workers=None):
        self.repository = CharacterSessionRepository(directory, validator=validate_supported_session,
                                                     supported_schemas=(1, 2))
        self.slots = ProviderSlots(4)
        self.legacy = CharacterChatService(self.repository, transport, recover=False,
                                          preference_loader=preference_loader, slots=self.slots)
        self.groups = CharacterGroupService(self.repository, transport,
                                           preference_loader=preference_loader, slots=self.slots)
        self.proactive = ProactiveContactService(self.groups, self.repository.directory.parent / 'proactive_quota.json')
        self.groups.proactive = self.proactive
        self.workers = workers if workers is not None else os.environ.get('WEB_CONCURRENCY', '1')
        self.started = False
        self.closed = False
        self.loop = None

    def require_groups(self):
        if not self.started or self.closed or self.loop is not asyncio.get_running_loop():
            raise CharacterSessionError('SERVICE_UNAVAILABLE')
        try:
            single_process = int(self.workers) == 1
        except (ValueError, TypeError):
            single_process = False
        if not single_process:
            raise CharacterSessionError('SERVICE_UNAVAILABLE')
        return self.groups

    async def start(self):
        if self.started or self.closed:
            return
        self.loop = asyncio.get_running_loop()
        self.legacy.recover_pending()
        # Multi-process deployments may inspect data but must not start C4
        # recovery timers, writes or subscriptions on competing processes.
        try:
            single_process = int(self.workers) == 1
        except (ValueError, TypeError):
            single_process = False
        if single_process:
            await self.groups.start()
            await self.proactive.start()
        self.started = True

    def require_proactive(self):
        self.require_groups()
        return self.proactive

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.legacy.closed = True
        failure = None
        try:
            await self.proactive.close()
        except Exception as exc:
            failure = exc
        try:
            await self.groups.close()
        except Exception as exc:
            failure = failure or exc
        for rid, job in list(self.legacy.jobs.items()):
            try:
                self.legacy._terminal(job['session']['session_id'], job['action_id'], rid,
                                      'interrupted', 'PROCESS_INTERRUPTED')
            except Exception as exc:
                failure = failure or exc
        tasks = list(self.legacy.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # Requests admitted immediately before shutdown may not have entered
        # execute yet. Retire those reservations once, without a model call.
        for rid, job in list(self.legacy.jobs.items()):
            self.legacy.jobs.pop(rid, None)
            self.slots.release()
        if failure:
            raise failure


def runtime_lifespan(factory):
    @asynccontextmanager
    async def lifespan(app):
        runtime = factory()
        app.state.character_runtime = runtime
        try:
            await runtime.start()
            yield
        finally:
            await runtime.close()
    return lifespan
