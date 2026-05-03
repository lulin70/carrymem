"""Tests for async_carrymem.py - Async API wrapper"""

import pytest
from unittest.mock import patch
from memory_classification_engine.async_carrymem import AsyncCarryMem


@pytest.fixture
def mock_carrymem():
    with patch('memory_classification_engine.async_carrymem.CarryMem') as mock:
        yield mock


@pytest.mark.asyncio
async def test_init(mock_carrymem):
    async_cm = AsyncCarryMem(storage="sqlite", namespace="test")
    assert async_cm._sync is not None


@pytest.mark.asyncio
async def test_classify_message(mock_carrymem):
    mock_carrymem.return_value.classify_message.return_value = {"type": "fact"}
    async_cm = AsyncCarryMem()
    result = await async_cm.classify_message("test")
    assert result == {"type": "fact"}


@pytest.mark.asyncio
async def test_classify_and_remember(mock_carrymem):
    mock_carrymem.return_value.classify_and_remember.return_value = {"id": "123"}
    async_cm = AsyncCarryMem()
    result = await async_cm.classify_and_remember("test")
    assert result == {"id": "123"}


@pytest.mark.asyncio
async def test_recall_memories(mock_carrymem):
    mock_carrymem.return_value.recall_memories.return_value = [{"id": "1"}]
    async_cm = AsyncCarryMem()
    result = await async_cm.recall_memories("query")
    assert result == [{"id": "1"}]


@pytest.mark.asyncio
async def test_forget_memory(mock_carrymem):
    mock_carrymem.return_value.forget_memory.return_value = True
    async_cm = AsyncCarryMem()
    result = await async_cm.forget_memory("123")
    assert result is True


@pytest.mark.asyncio
async def test_get_stats(mock_carrymem):
    mock_carrymem.return_value.get_stats.return_value = {"count": 10}
    async_cm = AsyncCarryMem()
    result = await async_cm.get_stats()
    assert result == {"count": 10}


@pytest.mark.asyncio
async def test_declare(mock_carrymem):
    mock_carrymem.return_value.declare.return_value = {"id": "456"}
    async_cm = AsyncCarryMem()
    result = await async_cm.declare("decl")
    assert result == {"id": "456"}


@pytest.mark.asyncio
async def test_get_memory_profile(mock_carrymem):
    mock_carrymem.return_value.get_memory_profile.return_value = {"profile": "data"}
    async_cm = AsyncCarryMem()
    result = await async_cm.get_memory_profile()
    assert result == {"profile": "data"}


@pytest.mark.asyncio
async def test_build_context(mock_carrymem):
    mock_carrymem.return_value.build_context.return_value = {"context": "built"}
    async_cm = AsyncCarryMem()
    result = await async_cm.build_context("test")
    assert result == {"context": "built"}


@pytest.mark.asyncio
async def test_build_system_prompt(mock_carrymem):
    mock_carrymem.return_value.build_system_prompt.return_value = "prompt"
    async_cm = AsyncCarryMem()
    result = await async_cm.build_system_prompt("test")
    assert result == "prompt"


@pytest.mark.asyncio
async def test_export_memories(mock_carrymem):
    mock_carrymem.return_value.export_memories.return_value = {"exported": True}
    async_cm = AsyncCarryMem()
    result = await async_cm.export_memories("/path")
    assert result == {"exported": True}


@pytest.mark.asyncio
async def test_import_memories(mock_carrymem):
    mock_carrymem.return_value.import_memories.return_value = {"imported": 5}
    async_cm = AsyncCarryMem()
    result = await async_cm.import_memories("/path")
    assert result == {"imported": 5}


@pytest.mark.asyncio
async def test_update_memory(mock_carrymem):
    mock_carrymem.return_value.update_memory.return_value = {"updated": True}
    async_cm = AsyncCarryMem()
    result = await async_cm.update_memory("key", "new")
    assert result == {"updated": True}


@pytest.mark.asyncio
async def test_get_memory_history(mock_carrymem):
    mock_carrymem.return_value.get_memory_history.return_value = [{"v": 1}]
    async_cm = AsyncCarryMem()
    result = await async_cm.get_memory_history("key")
    assert result == [{"v": 1}]


@pytest.mark.asyncio
async def test_rollback_memory(mock_carrymem):
    mock_carrymem.return_value.rollback_memory.return_value = {"rolled_back": True}
    async_cm = AsyncCarryMem()
    result = await async_cm.rollback_memory("key", 1)
    assert result == {"rolled_back": True}


@pytest.mark.asyncio
async def test_backup(mock_carrymem):
    mock_carrymem.return_value.backup.return_value = {"backup": "done"}
    async_cm = AsyncCarryMem()
    result = await async_cm.backup("/dir")
    assert result == {"backup": "done"}


@pytest.mark.asyncio
async def test_get_audit_log(mock_carrymem):
    mock_carrymem.return_value.get_audit_log.return_value = [{"op": "add"}]
    async_cm = AsyncCarryMem()
    result = await async_cm.get_audit_log()
    assert result == [{"op": "add"}]


@pytest.mark.asyncio
async def test_close(mock_carrymem):
    mock_carrymem.return_value.close.return_value = None
    async_cm = AsyncCarryMem()
    await async_cm.close()
    mock_carrymem.return_value.close.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager(mock_carrymem):
    mock_carrymem.return_value.close.return_value = None
    async with AsyncCarryMem() as async_cm:
        assert async_cm is not None
    mock_carrymem.return_value.close.assert_called_once()
