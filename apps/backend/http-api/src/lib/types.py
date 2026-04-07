from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ErrorDetail:
    """A single structured error to include in an API error response."""

    message: str
    field: Optional[str] = None
    code: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict.

        Returns:
            Dict with message, and optionally field and code.
        """
        d = {"message": self.message}
        if self.field is not None:
            d["field"] = self.field
        if self.code is not None:
            d["code"] = self.code
        return d


@dataclass
class ApiResponse:
    """Standard API response envelope used by all v2 endpoints."""

    data: Any = None
    errors: List[ErrorDetail] = field(default_factory=list)
    page: Optional[int] = None
    total_pages: Optional[int] = None
    total_results: Optional[int] = None
    results_per_page: Optional[int] = None

    @classmethod
    def ok(cls, data: Any) -> "ApiResponse":
        """Create a successful response wrapping the given data.

        Args:
            data: The response payload.

        Returns:
            ApiResponse with data set and no errors.
        """
        return cls(data=data)

    @classmethod
    def created(cls, data: Any) -> "ApiResponse":
        """Create a 201 Created response wrapping the new resource.

        Args:
            data: The newly created resource payload.

        Returns:
            ApiResponse with data set and no errors.
        """
        return cls(data=data)

    @classmethod
    def deleted(cls) -> "ApiResponse":
        """Create a response for a successful deletion (null data).

        Returns:
            ApiResponse with data=None and no errors.
        """
        return cls(data=None)

    @classmethod
    def paginated(
        cls,
        data: Any,
        page: int,
        total_pages: int,
        total_results: int,
        results_per_page: int,
    ) -> "ApiResponse":
        """Create a paginated list response.

        Args:
            data: The page of results.
            page: Current page number (1-indexed).
            total_pages: Total number of pages.
            total_results: Total number of items across all pages.
            results_per_page: Number of items per page.

        Returns:
            ApiResponse with pagination metadata.
        """
        return cls(
            data=data,
            page=page,
            total_pages=total_pages,
            total_results=total_results,
            results_per_page=results_per_page,
        )

    @classmethod
    def error(cls, *errors: ErrorDetail) -> "ApiResponse":
        """Create an error response with one or more ErrorDetail instances.

        Args:
            *errors: One or more ErrorDetail instances.

        Returns:
            ApiResponse with data=None and errors populated.
        """
        return cls(data=None, errors=list(errors))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict for Flask jsonify.

        Returns:
            Dict with data, errors, and optional pagination fields.
        """
        d: Dict[str, Any] = {
            "data": self.data,
            "errors": [e.to_dict() for e in self.errors],
        }
        if self.page is not None:
            d["page"] = self.page
        if self.total_pages is not None:
            d["totalPages"] = self.total_pages
        if self.total_results is not None:
            d["totalResults"] = self.total_results
        if self.results_per_page is not None:
            d["resultsPerPage"] = self.results_per_page
        return d
