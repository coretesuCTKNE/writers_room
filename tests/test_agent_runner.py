"""Tests for agent_runner.py."""

import pytest


class TestAgentRunner:
    @pytest.mark.asyncio
    async def test_run_agent_unknown(self):
        from greenlight.api.services.agent_runner import run_agent

        result = await run_agent("nonexistent_agent", "test prompt")
        assert "error" in result
        assert "Unknown agent" in result["error"]

    @pytest.mark.asyncio
    async def test_broker_subscribe_publish(self):
        from greenlight.api.services.agent_runner import AgentBroker, AgentEvent

        broker = AgentBroker()
        queue = await broker.subscribe()

        event = AgentEvent(agent="reader", status="running", message="test")
        await broker.publish(event)

        assert not queue.empty()
        received = queue.get_nowait()
        assert received.agent == "reader"
        assert received.status == "running"

        await broker.unsubscribe(queue)
        assert queue not in broker._subscribers

    @pytest.mark.asyncio
    async def test_broker_multiple_subscribers(self):
        from greenlight.api.services.agent_runner import AgentBroker, AgentEvent

        broker = AgentBroker()
        q1 = await broker.subscribe()
        q2 = await broker.subscribe()

        event = AgentEvent(agent="bible", status="completed")
        await broker.publish(event)

        assert not q1.empty()
        assert not q2.empty()

        await broker.unsubscribe(q1)
        await broker.unsubscribe(q2)
