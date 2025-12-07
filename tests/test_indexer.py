"""
Tests for the indexer module.
"""

from unittest.mock import MagicMock, patch

import pytest

from athenaeum.indexer import build_index


@pytest.fixture
def mock_vector_store():
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_index():
    mock = MagicMock()
    mock.docstore.docs.values.return_value = [MagicMock(nodes=[1, 2, 3])]
    return mock


@patch("athenaeum.indexer._validate_paths")
@patch("athenaeum.indexer.setup_settings")
@patch("athenaeum.indexer._build_document_reader")
@patch("athenaeum.indexer._create_faiss_storage")
@patch("athenaeum.indexer.VectorStoreIndex.from_documents")
@patch("athenaeum.indexer._persist_index")
@patch("athenaeum.indexer._generate_stats")
def test_build_index(
    mock_stats,
    mock_persist,
    mock_vector_index,
    mock_storage,
    mock_reader,
    mock_setup,
    mock_validate,
    tmp_path,
    mock_index,
):
    # Setup mocks
    mock_validate.return_value = [tmp_path]
    mock_reader.return_value.load_data.return_value = ["doc1", "doc2"]
    mock_vector_index.return_value = mock_index
    mock_stats.return_value = {"documents_ingested": 2}

    # Call the function
    result = build_index([tmp_path], tmp_path, return_stats=True)

    # Verify expected function calls
    mock_validate.assert_called_once_with([tmp_path])
    mock_setup.assert_called_once()
    mock_reader.assert_called_once()
    mock_storage.assert_called_once_with(tmp_path)
    mock_vector_index.assert_called_once()
    mock_persist.assert_called_once()
    mock_stats.assert_called_once_with(["doc1", "doc2"], mock_index)

    # Check result
    assert result["documents_ingested"] == 2


@patch("athenaeum.indexer._validate_paths")
@patch("athenaeum.indexer._build_document_reader")
@patch("athenaeum.indexer.setup_settings")
def test_build_index_no_documents(_mock_setup, mock_reader, mock_validate, tmp_path):
    # Setup mocks
    mock_validate.return_value = [tmp_path]
    mock_reader.return_value.load_data.return_value = []

    # Call the function with no documents
    result = build_index([tmp_path], tmp_path, return_stats=True)

    # Verify result contains warning
    assert result is not None
    assert "warning" in result  # type: ignore[operator]
    assert "No documents" in result["warning"]  # type: ignore[index]
