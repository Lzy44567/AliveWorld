"""Asynchronous provider calls with bounded establishment retries and private traces."""
import asyncio
import time
from openai import AsyncOpenAI, APITimeoutError, RateLimitError, BadRequestError
from core.llm_trace import begin_llm_trace, finish_llm_trace
from core.model_connections.runtime import get_task_connection
from core.request_budget import normalize_usage
from core.provider_retry import request_with_retry_async
from .models import CharacterSessionError
from .stream_json import ReplyPreview
from .group_stream import GroupPreview
from .protocol import V3, validate_contract
from .context_contract import validate_context_contract, LEGACY, ContextContractError


class CharacterTransport:
    def snapshot(self):
        connection = get_task_connection('character')
        if not connection or connection.profile.protocol != 'openai_compatible' or not connection.profile.enabled:
            raise CharacterSessionError('CONNECTION_UNSUPPORTED')
        config = connection.ai_config()
        if not config.get('base_url') or not config.get('model'):
            raise CharacterSessionError('CONNECTION_UNSUPPORTED')
        if not connection.profile.api_key and connection.profile.provider_hint != 'local':
            raise CharacterSessionError('CONNECTION_UNSUPPORTED')
        return config

    async def generate(self, config, plan, report, delivery, emit):
        try:
            validate_context_contract(plan.context_contract_id if plan.context_contract_id is not None else LEGACY)
        except ContextContractError:
            raise CharacterSessionError('CONTEXT_CONTRACT_UNSUPPORTED') from None
        try:
            validate_contract(plan.contract_id)
        except ValueError:
            raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED') from None
        return await self._generate(config, plan, report, delivery, emit, 'character.reply')

    async def generate_contact(self, config, plan, report):
        """One explicitly authorized non-stream contact planning request."""
        if (plan.contract_id != 'character.contact_plan.v1' or
                plan.context_contract_id != 'character.contact_context.v1'):
            raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
        return await self._generate(config, plan, report, 'non_stream', lambda *_: None, 'character.contact')

    async def generate_summary(self, config, plan, report):
        return await self._generate(config, plan, report, 'non_stream', lambda *_: None, 'character.compaction')

    async def _generate(self, config, plan, report, delivery, emit, trace_kind):
        trace = begin_llm_trace(trace_kind, config['model'], '[private content omitted]',
                                '[private content omitted]', 'json', plan.prompt_manifest)
        started, usage, error = time.monotonic(), None, None
        retries = config.get('automatic_retries', 0) if trace_kind == 'character.reply' else 0
        try:
            async with AsyncOpenAI(api_key=config['api_key'], base_url=config['base_url'], max_retries=0, timeout=60.0) as client:
                kwargs = {'model': config['model'], 'messages': [
                    {'role': 'system', 'content': plan.system_prompt}, {'role': 'user', 'content': plan.user_prompt}],
                    'temperature': plan.temperature, 'max_tokens': report['outputReserve'],
                    'response_format': {'type': 'json_object'}}
                async with asyncio.timeout(180):
                    if delivery == 'non_stream':
                        response = await request_with_retry_async(lambda: client.chat.completions.create(**kwargs), retries)
                        if len(response.choices) != 1:
                            raise CharacterSessionError('CONTRACT_INVALID')
                        choice = response.choices[0]
                        if choice.finish_reason != 'stop':
                            raise CharacterSessionError('PROVIDER_TRUNCATED')
                        if choice.message.tool_calls or getattr(choice.message, 'function_call', None):
                            raise CharacterSessionError('CONTRACT_INVALID')
                        raw = choice.message.content or ''
                        usage = response.usage.model_dump() if response.usage else None
                        if len(raw.encode('utf-8')) > 65536:
                            raise CharacterSessionError('CONTRACT_INVALID')
                        return raw
                    stream = await request_with_retry_async(lambda: client.chat.completions.create(**kwargs, stream=True), retries)
                    preview = GroupPreview(emit) if plan.contract_id == V3 else ReplyPreview(emit, plan.contract_id)
                    parts, finish, count = [], None, 0
                    last_content = time.monotonic()
                    try:
                        iterator = stream.__aiter__()
                        while True:
                            try:
                                remaining = 60 - (time.monotonic() - last_content)
                                if remaining <= 0:
                                    raise TimeoutError()
                                chunk = await asyncio.wait_for(anext(iterator), remaining)
                            except StopAsyncIteration:
                                break
                            count += 1
                            if count > 10000 or len(chunk.choices) > 1:
                                raise CharacterSessionError('CONTRACT_INVALID')
                            if chunk.usage:
                                usage = chunk.usage.model_dump()
                            for choice in chunk.choices:
                                if choice.index != 0 or choice.delta.tool_calls or getattr(choice.delta, 'function_call', None):
                                    raise CharacterSessionError('CONTRACT_INVALID')
                                content = choice.delta.content
                                if content:
                                    last_content = time.monotonic()
                                    if finish is not None:
                                        raise CharacterSessionError('CONTRACT_INVALID')
                                    parts.append(content)
                                    preview.feed(content)
                                if choice.finish_reason:
                                    if finish is not None or choice.finish_reason != 'stop':
                                        raise CharacterSessionError('PROVIDER_TRUNCATED')
                                    finish = 'stop'
                        if finish != 'stop':
                            raise CharacterSessionError('PROVIDER_TRUNCATED')
                        return ''.join(parts)
                    finally:
                        await stream.close()
        except asyncio.CancelledError:
            error = 'USER_CANCELLED'
            raise
        except (APITimeoutError, TimeoutError):
            error = 'PROVIDER_TIMEOUT'
            raise CharacterSessionError(error) from None
        except RateLimitError:
            error = 'PROVIDER_RATE_LIMIT'
            raise CharacterSessionError(error) from None
        except BadRequestError:
            error = 'STREAM_UNSUPPORTED' if delivery == 'stream' else 'PROVIDER_FAILED'
            raise CharacterSessionError(error) from None
        except CharacterSessionError as exc:
            error = exc.code
            raise
        except Exception:
            error = 'PROVIDER_FAILED'
            raise CharacterSessionError(error) from None
        finally:
            finish_llm_trace(trace_kind, trace, response='[private content omitted]', error=error,
                             metadata={'budget': report, 'usage': usage, 'normalizedUsage': normalize_usage(usage),
                                       'elapsedMs': round((time.monotonic() - started) * 1000), 'attempt': 1})
