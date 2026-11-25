def test_infinite_schema_exported():
    from app.schema import ArticleInfiniteOut, decode_cursor, encode_cursor

    cur = encode_cursor(None, 42)
    assert decode_cursor(cur)["id"] == 42
