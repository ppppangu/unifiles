"""File feature use cases that are independent of HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportedFileTypesResult:
    document_types: tuple[str, ...]
    image_types: tuple[str, ...]

    @property
    def all_types(self) -> tuple[str, ...]:
        return self.document_types + self.image_types


class FilesService:
    def list_supported_file_types(self) -> SupportedFileTypesResult:
        return SupportedFileTypesResult(
            document_types=(".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".xml"),
            image_types=(".png", ".jpg", ".jpeg", ".tiff", ".webp"),
        )
