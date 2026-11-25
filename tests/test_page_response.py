"""PageResponse.total_pages：传统分页「尾页」直接跳转的依据（ceil(total/page_size)）"""
from app.schema.common import page_response


def test_total_pages_is_ceil_of_total_over_page_size():
    assert page_response([1], total=10, page=1, page_size=3).total_pages == 4
    assert page_response([1], total=9, page=3, page_size=3).total_pages == 3


def test_total_pages_is_zero_when_nothing_matches():
    assert page_response([], total=0, page=1, page_size=20).total_pages == 0
