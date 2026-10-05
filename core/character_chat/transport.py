"""One asynchronous provider call, zero retries and content-minimized tracing."""
import asyncio
import time
from openai import AsyncOpenAI, APITimeoutError, RateLimitError, BadRequestError
from core.llm_trace import begin_llm_trace, finish_llm_trace
from core.model_connections.runtime import get_task_connection
from core.request_budget import normalize_usage
from .models import CharacterSessionError
from .stream_json import ReplyPreview
from .protocol import validate_contract
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
        trace = begin_llm_trace('character.reply', config['model'], '[private content omitted]',
                                '[private content omitted]', 'json', plan.prompt_manifest)
        started, usage, error = time.monotonic(), None, None
        try:
            async with AsyncOpenAI(api_key=config['api_key'], base_url=config['base_url'], max_retries=0, timeout=60.0) as client:
                kwargs = {'model': config['model'], 'messages': [
                    {'role': 'system', 'content': plan.system_prompt}, {'role': 'user', 'content': plan.user_prompt}],
                    'temperature': plan.temperature, 'max_tokens': report['outputReserve'],
                    'response_format': {'type': 'json_object'}}
                async with asyncio.timeout(180):
                    if delivery == 'non_stream':
                        response = await client.chat.completions.create(**kwargs)
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
                    stream = await client.chat.completions.create(**kwargs, stream=True)
                    preview = ReplyPreview(emit, plan.contract_id)
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
            finish_llm_trace('character.reply', trace, response='[private content omitted]', error=error,
                             metadata={'budget': report, 'usage': usage, 'normalizedUsage': normalize_usage(usage),
                                       'elapsedMs': round((time.monotonic() - started) * 1000), 'attempt': 1})
