"""Tests for embedding validation logic in the data pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from adalflow.core.types import Document

from deepwiki_cli.services import data_pipeline

if TYPE_CHECKING:
    from pathlib import Path


def _make_doc(path: str, *, vector: list[float] | None = None) -> Document:
    doc = Document(text=f"doc:{path}", meta_data={"file_path": path})
    if vector is not None:
        doc.vector = vector
    return doc


def test_require_valid_embeddings_filters_missing() -> None:
    docs = [_make_doc("valid", vector=[0.1, 0.2]), _make_doc("invalid")]

    filtered = data_pipeline._require_valid_embeddings(
        docs,
        embedder_type="openai",
        context="unit-test",
    )

    assert len(filtered) == 1
    assert filtered[0].meta_data["file_path"] == "valid"


def test_require_valid_embeddings_raises_when_all_missing() -> None:
    docs = [_make_doc("missing"), _make_doc("missing-2")]

    with pytest.raises(ValueError, match="No embeddings were produced"):
        data_pipeline._require_valid_embeddings(
            docs,
            embedder_type="openai",
            context="unit-test",
        )


def test_transform_documents_and_save_to_db_fails_without_vectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = [_make_doc("file_a")]  # vector missing after transform
    transformed: list[Document] = [_make_doc("chunk_a")]

    class DummyDB:
        def __init__(self) -> None:
            self.transformed_items: dict[str, list[Document]] = {}

        def register_transformer(self, transformer, key: str) -> None:
            self.key = key

        def load(self, docs: list[Document]) -> None:
            self.docs = docs

        def transform(self, key: str) -> None:
            self.transformed_items[key] = transformed

        def get_transformed_data(self, key: str) -> list[Document]:
            return self.transformed_items.get(key, [])

        def save_state(self, filepath: str) -> None:
            self.filepath = filepath

    monkeypatch.setattr(data_pipeline, "LocalDB", DummyDB)
    monkeypatch.setattr(
        data_pipeline,
        "prepare_data_pipeline",
        lambda *_, **__: object(),
    )

    with pytest.raises(ValueError):
        data_pipeline.transform_documents_and_save_to_db(
            documents,
            str(tmp_path / "db.pkl"),
            embedder_type="openai",
        )


def test_transform_documents_and_save_to_db_filters_invalid_vectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = [_make_doc("file_a"), _make_doc("file_b")]
    valid_chunk = _make_doc("file_a", vector=[0.1, 0.2])
    invalid_chunk = _make_doc("file_b")
    transformed: list[Document] = [valid_chunk, invalid_chunk]

    class DummyDB:
        def __init__(self) -> None:
            self.transformed_items: dict[str, list[Document]] = {}

        def register_transformer(self, transformer, key: str) -> None:
            self.key = key

        def load(self, docs: list[Document]) -> None:
            self.docs = docs

        def transform(self, key: str) -> None:
            self.transformed_items[key] = list(transformed)

        def get_transformed_data(self, key: str) -> list[Document]:
            return self.transformed_items.get(key, [])

        def save_state(self, filepath: str) -> None:
            self.filepath = filepath

    monkeypatch.setattr(data_pipeline, "LocalDB", DummyDB)
    monkeypatch.setattr(
        data_pipeline,
        "prepare_data_pipeline",
        lambda *_, **__: object(),
    )

    db = data_pipeline.transform_documents_and_save_to_db(
        documents,
        str(tmp_path / "db.pkl"),
        embedder_type="openai",
    )

    saved_docs = db.get_transformed_data(key="split_and_embed")
    assert len(saved_docs) == 1
    assert saved_docs[0].meta_data["file_path"] == "file_a"
