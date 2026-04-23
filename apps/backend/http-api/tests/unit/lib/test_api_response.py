"""
Unit tests for ApiResponse in src/lib/types.py.

Tests response construction and serialization with camelCase conversion.
"""

import pytest


def test_api_response_ok():
    from src.lib.types import ApiResponse

    data = {"id": "123", "name": "Test Product"}
    response = ApiResponse.ok(data)

    assert response.data == data
    assert response.errors == []
    assert response.page is None
    assert response.total_pages is None


def test_api_response_created():
    from src.lib.types import ApiResponse

    data = {"id": "456", "status": "created"}
    response = ApiResponse.created(data)

    assert response.data == data
    assert response.errors == []


def test_api_response_deleted():
    from src.lib.types import ApiResponse

    response = ApiResponse.deleted()

    assert response.data is None
    assert response.errors == []


def test_api_response_error_single():
    from src.lib.types import ApiResponse, ErrorDetail

    error = ErrorDetail(message="Invalid input", field="name", code="INVALID")
    response = ApiResponse.error(error)

    assert response.data is None
    assert len(response.errors) == 1
    assert response.errors[0].message == "Invalid input"
    assert response.errors[0].field == "name"
    assert response.errors[0].code == "INVALID"


def test_api_response_error_multiple():
    from src.lib.types import ApiResponse, ErrorDetail

    error1 = ErrorDetail(message="Name is required", field="name")
    error2 = ErrorDetail(message="Email is invalid", field="email")
    response = ApiResponse.error(error1, error2)

    assert response.data is None
    assert len(response.errors) == 2
    assert response.errors[0].message == "Name is required"
    assert response.errors[1].message == "Email is invalid"


def test_api_response_paginated():
    from src.lib.types import ApiResponse

    data = [{"id": "1"}, {"id": "2"}]
    response = ApiResponse.paginated(
        data=data,
        page=2,
        total_pages=10,
        total_results=100,
        results_per_page=10,
    )

    assert response.data == data
    assert response.page == 2
    assert response.total_pages == 10
    assert response.total_results == 100
    assert response.results_per_page == 10
    assert response.errors == []


def test_api_response_to_dict_basic():
    from src.lib.types import ApiResponse

    data = {"id": "123"}
    response = ApiResponse.ok(data)
    result = response.to_dict()

    assert result["data"] == data
    assert result["errors"] == []
    assert "page" not in result
    assert "totalPages" not in result


def test_api_response_to_dict_paginated_camelcase():
    from src.lib.types import ApiResponse

    data = [{"id": "1"}]
    response = ApiResponse.paginated(
        data=data,
        page=1,
        total_pages=5,
        total_results=50,
        results_per_page=10,
    )
    result = response.to_dict()

    assert result["data"] == data
    assert result["page"] == 1
    assert result["totalPages"] == 5  # camelCase
    assert result["totalResults"] == 50  # camelCase
    assert result["resultsPerPage"] == 10  # camelCase
    assert result["errors"] == []


def test_error_detail_to_dict():
    from src.lib.types import ErrorDetail

    error = ErrorDetail(message="Test error", field="testField", code="TEST_CODE")
    result = error.to_dict()

    assert result["message"] == "Test error"
    assert result["field"] == "testField"
    assert result["code"] == "TEST_CODE"


def test_error_detail_to_dict_minimal():
    from src.lib.types import ErrorDetail

    error = ErrorDetail(message="Simple error")
    result = error.to_dict()

    assert result["message"] == "Simple error"
    assert "field" not in result
    assert "code" not in result


def test_error_detail_to_dict_with_field_only():
    from src.lib.types import ErrorDetail

    error = ErrorDetail(message="Field error", field="email")
    result = error.to_dict()

    assert result["message"] == "Field error"
    assert result["field"] == "email"
    assert "code" not in result


def test_error_detail_to_dict_with_code_only():
    from src.lib.types import ErrorDetail

    error = ErrorDetail(message="Coded error", code="ERR_001")
    result = error.to_dict()

    assert result["message"] == "Coded error"
    assert result["code"] == "ERR_001"
    assert "field" not in result


def test_api_response_to_dict_with_errors():
    from src.lib.types import ApiResponse, ErrorDetail

    error1 = ErrorDetail(message="Error 1", field="field1")
    error2 = ErrorDetail(message="Error 2", code="CODE_2")
    response = ApiResponse.error(error1, error2)
    result = response.to_dict()

    assert result["data"] is None
    assert len(result["errors"]) == 2
    assert result["errors"][0]["message"] == "Error 1"
    assert result["errors"][0]["field"] == "field1"
    assert result["errors"][1]["message"] == "Error 2"
    assert result["errors"][1]["code"] == "CODE_2"


def test_api_response_error_with_raw_string_crashes():
    """Verify that passing a raw string to ApiResponse.error() crashes on to_dict().

    This documents the bug that existed when endpoints called
    ApiResponse.error("some string") instead of
    ApiResponse.error(ErrorDetail(message="some string")).
    """
    from src.lib.types import ApiResponse

    response = ApiResponse.error("raw string error")
    with pytest.raises(AttributeError, match="to_dict"):
        response.to_dict()
