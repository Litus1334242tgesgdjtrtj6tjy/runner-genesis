import pytest

from runner_genesis.ingestion.parsed_stream import HeliusParsedStreamSubscriber


class FailingContext:
    async def __aenter__(self):
        raise OSError("temporary disconnect")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        return '{"jsonrpc":"2.0","result":1,"id":1}'

    def __aiter__(self):
        self._done = False
        return self

    async def __anext__(self):
        if self._done:
            raise StopAsyncIteration
        self._done = True
        return '{"params":{"result":{"value":{"signature":"sig","summary":{"type":"swap"}}}}}'


class SuccessContext:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_parsed_stream_request_uses_program_filter():
    sub = HeliusParsedStreamSubscriber("key", ["PUMP", "PUMPSWAP"])
    req = sub._request()
    assert req["method"] == "parsedTransactionSubscribe"
    assert req["params"][0]["programs"] == ["PUMP", "PUMPSWAP"]
    assert req["params"][0]["includeFailed"] is False


@pytest.mark.asyncio
async def test_parsed_stream_reconnects_after_transport_failure(monkeypatch):
    ws = FakeWS()
    calls = {"n": 0, "sleeps": 0}

    def fake_connect(*args, **kwargs):
        calls["n"] += 1
        return FailingContext() if calls["n"] == 1 else SuccessContext(ws)

    async def fake_sleep(_delay):
        calls["sleeps"] += 1

    monkeypatch.setattr("runner_genesis.ingestion.parsed_stream.websockets.connect", fake_connect)
    monkeypatch.setattr("runner_genesis.ingestion.parsed_stream.asyncio.sleep", fake_sleep)

    sub = HeliusParsedStreamSubscriber("key", ["PUMP"], reconnect_min_seconds=0.1)
    gen = sub.payloads()
    payload = await anext(gen)
    await gen.aclose()

    assert payload["signature"] == "sig"
    assert calls["n"] == 2
    assert calls["sleeps"] == 1
    assert ws.sent
