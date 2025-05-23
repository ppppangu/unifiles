import asyncio

import pytest

from src.chunks import create_text_chunks, embed_chunks


@pytest.mark.parametrize(
    "text_len,chunk_size,overlap,expected_chunks",
    [
        (500, 1000, 200, 1),  # 不足 chunk_size
        (1000, 1000, 200, 1),
        (1100, 1000, 200, 2),  # 需要 2 块
    ],
)
def test_create_text_chunks_basic(text_len, chunk_size, overlap, expected_chunks):
    pages = ["a" * text_len]
    chunks = create_text_chunks(pages, chunk_size=chunk_size, overlap=overlap)
    assert len(chunks) == expected_chunks


@pytest.mark.asyncio
async def test_embed_chunks_mock(monkeypatch):
    """通过 monkeypatch 模拟远程嵌入接口，确保长度一致"""

    async def fake_request(text, session):
        return [0.0, 1.0, 2.0]  # 固定维度向量

    # 替换内部私有函数
    monkeypatch.setattr("src.chunks._embedding_request", fake_request)

    chunks = ["hello", "world"]
    res = await embed_chunks(chunks)
    assert len(res) == len(chunks)
    for vec in res:
        assert vec == [0.0, 1.0, 2.0] 