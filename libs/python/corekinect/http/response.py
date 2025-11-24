import json
from typing import Any, List, Optional


class ConcordHttpResponse:
    """
    Structured format for every API response. Contains data, errors, and pagination.
    """

    def __init__(
        self,
        data: Any = None,
        errors: Optional[List[Any]] = None,
        page: Optional[int] = None,
        total_pages: Optional[int] = None,
        total_results: Optional[int] = None,
        results_per_page: Optional[int] = None,
    ):
        self.data = data
        self.errors = errors or []
        self.page = page
        self.total_pages = total_pages
        self.total_results = total_results
        self.results_per_page = results_per_page

    @classmethod
    def new_get_response(cls, data: Any) -> "ConcordHttpResponse":
        """
        Creates a new API response object for a GET (Object) route.
        The data parameter should be a unique instance of a struct.
        """
        return cls(data=data, errors=None)

    @classmethod
    def new_list_response(
        cls,
        data: Any,
        page: Optional[int] = None,
        total_pages: Optional[int] = None,
        total_results: Optional[int] = None,
        results_per_page: Optional[int] = None,
    ) -> "ConcordHttpResponse":
        """
        Creates a new API response object for a GET (List) route.
        The data parameter should be a list/slice.
        """
        return cls(
            data=data,
            errors=None,
            page=page,
            total_pages=total_pages,
            total_results=total_results,
            results_per_page=results_per_page,
        )

    @classmethod
    def new_create_response(cls, data: Any) -> "ConcordHttpResponse":
        """
        Creates a new API response object for a POST route.
        """
        return cls(data=data, errors=None)

    @classmethod
    def new_update_response(cls, data: Any, errors: Optional[List[Any]] = None) -> "ConcordHttpResponse":
        """
        Creates a new API response object for a PUT or PATCH route.
        """
        return cls(data=data, errors=errors)

    @classmethod
    def new_delete_response(cls) -> "ConcordHttpResponse":
        """
        Creates a new API response object for a DELETE route.
        """
        return cls(data=None, errors=None)

    def to_dict(self) -> dict:
        """
        Converts the API response instance to a dictionary.
        """
        response_dict = {"data": self.data, "errors": self.errors}

        # Only include pagination fields if they are not None
        if self.page is not None:
            response_dict["page"] = self.page
        if self.total_pages is not None:
            response_dict["totalPages"] = self.total_pages
        if self.total_results is not None:
            response_dict["totalResults"] = self.total_results
        if self.results_per_page is not None:
            response_dict["resultsPerPage"] = self.results_per_page

        return response_dict

    def to_json(self) -> str:
        """
        Marshals the API response instance to a JSON string.
        """
        return json.dumps(self.to_dict())

    def marshal_json(self) -> tuple[bytes, Optional[Exception]]:
        """
        Marshals the API response instance to JSON bytes.
        Returns (json_bytes, error) tuple similar to Go's pattern.
        """
        try:
            json_bytes = json.dumps(self.to_dict()).encode("utf-8")
            return json_bytes, None
        except Exception as e:
            return b"", e
