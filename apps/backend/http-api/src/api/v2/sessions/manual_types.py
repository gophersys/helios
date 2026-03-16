from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class ValidationTestsRunRequest:
    """Request structure for running a validation test"""

    product: str
    zip_file_path: str
    additional_fields: Dict[str, str]

    @classmethod
    def from_form_data(cls, form_data: dict, zip_file_path: str) -> Tuple[Optional["ValidationTestsRunRequest"], Optional[str]]:
        """Parse form data into request object with validation"""
        if not form_data:
            return None, "Request must contain form data"

        product = form_data.get("product")
        if not product:
            return None, "Field 'product' is required"

        # Extract additional fields (excluding name, product, and file)
        additional_fields = {}
        for key, value in form_data.items():
            if key not in ["product", "file"] and value:
                additional_fields[key] = value

        return cls(product=product, zip_file_path=zip_file_path, additional_fields=additional_fields), None
