"""Tests for /ws/agents WebSocket hub."""


import pytest

from greenlight.api.services.agent_runner import AgentEvent, broker


class TestAgentBroker:
    @pytest.mark.asyncio
    async def test_subscribe_publish(self):
        queue = await broker.subscribe()
        event = AgentEvent(agent="reader", status="running", message="test")
        await broker.publish(event)

        assert not queue.empty()
        received = queue.get_nowait()
        assert received.agent == "reader"
        assert received.status == "running"

        await broker.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        q1 = await broker.subscribe()
        q2 = await broker.subscribe()

        event = AgentEvent(agent="bible", status="completed")
        await broker.publish(event)

        assert not q1.empty()
        assert not q2.empty()

        await broker.unsubscribe(q1)
        await broker.unsubscribe(q2)

    @pytest.mark.asyncio
    async def test_unsubscribe_cleans_up(self):
        before = len(broker._subscribers)
        q = await broker.subscribe()
        assert len(broker._subscribers) == before + 1

        await broker.unsubscribe(q)
        assert len(broker._subscribers) == before

    @pytest.mark.asyncio
    async def test_publish_does_not_block_when_subscriber_slow(self):
        from greenlight.api.services.agent_runner import AgentBroker

        small_broker = AgentBroker(max_queue_size=1)
        q = await small_broker.subscribe()

        await small_broker.publish(AgentEvent(agent="a", status="running"))
        await small_broker.publish(AgentEvent(agent="b", status="running"))
        await small_broker.publish(AgentEvent(agent="c", status="running"))

        assert q.qsize() == 1
        await small_broker.unsubscribe(q)
