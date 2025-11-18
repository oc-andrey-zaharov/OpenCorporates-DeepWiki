"""Tests covering DatabaseManager caching behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Never

from adalflow.core.types import Document

from deepwiki_cli.services import data_pipeline

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class DummyDB:
    """Simple stand-in for LocalDB used in caching tests."""

    def __init__(self, documents: list[Document]) -> None:
        self._documents = documents

    def get_transformed_data(self, key: str) -> list[Document]:
        """Return data stored in the dummy database regardless of key."""
        return self._documents


def test_prepare_db_index_recovers_from_missing_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupted pickles referencing unknown modules are quarantined and rebuilt.

    The cached pickle raises ModuleNotFoundError("api"), so the manager should
    move it aside, rebuild the index, and keep processing with the fresh data.
    """
    manager = data_pipeline.DatabaseManager()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("hello world")

    db_file = tmp_path / "db.pkl"
    db_file.write_text("corrupted")
    manager.repo_paths = {
        "save_db_file": str(db_file),
        "save_repo_dir": str(repo_dir),
    }

    def fake_load_state(cls: type[Any], filepath: str | None = None) -> Never:  # type: ignore[unused-argument]
        raise ModuleNotFoundError("No module named 'api'", name="api")

    monkeypatch.setattr(
        data_pipeline.LocalDB,
        "load_state",
        classmethod(fake_load_state),
    )

    documents = [Document(text="dummy", meta_data={"file_path": "README.md"})]

    monkeypatch.setattr(
        data_pipeline,
        "read_all_documents",
        lambda *_args, **_kwargs: documents,
    )

    def fake_transform(
        docs: list[Document],
        db_path: str,
        embedder_type: str | None = None,
        is_lmstudio_embedder: bool | None = None,
    ) -> DummyDB:
        return DummyDB(docs)

    monkeypatch.setattr(
        data_pipeline,
        "transform_documents_and_save_to_db",
        fake_transform,
    )

    transformed = manager.prepare_db_index()

    assert transformed == documents
    assert not db_file.exists()
    assert (tmp_path / "db.pkl.invalid").exists()
