from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ErrorDetail:
    message: str
    field: Optional[str] = None
    code: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"message": self.message}
        if self.field is not None:
            d["field"] = self.field
        if self.code is not None:
            d["code"] = self.code
        return d


@dataclass
class ApiResponse:
    data: Any = None
    errors: List[ErrorDetail] = field(default_factory=list)
    page: Optional[int] = None
    total_pages: Optional[int] = None
    total_results: Optional[int] = None
    results_per_page: Optional[int] = None

    @classmethod
    def ok(cls, data: Any) -> "ApiResponse":
        return cls(data=data)

    @classmethod
    def created(cls, data: Any) -> "ApiResponse":
        return cls(data=data)

    @classmethod
    def deleted(cls) -> "ApiResponse":
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
        return cls(
            data=data,
            page=page,
            total_pages=total_pages,
            total_results=total_results,
            results_per_page=results_per_page,
        )

    @classmethod
    def error(cls, *errors: ErrorDetail) -> "ApiResponse":
        return cls(data=None, errors=list(errors))

    def to_dict(self) -> Dict[str, Any]:
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
