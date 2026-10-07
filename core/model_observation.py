"""Request-scoped SDK usage observation; never store model reasoning or prompts."""
from contextvars import ContextVar
import time

model_events = ContextVar("cartcare_model_events", default=None)


class ObservedClient:
    def __init__(self, client, stage):
        self._client, self.stage = client, stage
        self.messages = self

    async def close(self):
        await self._client.close()

    async def create(self, **kwargs):
        events = model_events.get()
        event = {"stage": self.stage, "model": kwargs.get("model")}
        if events is not None:
            events.append(event)
        start = time.monotonic()
        try:
            response = await self._client.messages.create(**kwargs)
            usage = getattr(response, "usage", None)
            event.update(input_tokens=getattr(usage, "input_tokens", None),
                         output_tokens=getattr(usage, "output_tokens", None))
            return response
        except Exception as exc:
            event["error_type"] = type(exc).__name__
            raise
        finally:
            event["latency_ms"] = round((time.monotonic() - start) * 1000, 1)

