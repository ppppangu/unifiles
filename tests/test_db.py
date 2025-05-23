from unittest.mock import patch, MagicMock

import pytest

from src import db as db_mod


@pytest.mark.asyncio
@patch("psycopg2.connect")
async def test_insert_chunks_calls_db(connect_mock):
    # 准备 mock 连接与 cursor
    conn_mock = MagicMock()
    cursor_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    connect_mock.return_value = conn_mock

    chunks = ["foo"]
    embeddings = [[0.1, 0.2, 0.3]]

    await db_mod.insert_chunks(chunks, embeddings, "kb1", "doc1", user_id="user1")

    # 确保连接被调用
    connect_mock.assert_called_once()
    # 确保执行了删除旧 chunks 的 SQL
    assert any("DELETE FROM chunk_schema.chunks" in call.args[0] for call in cursor_mock.execute.call_args_list) 