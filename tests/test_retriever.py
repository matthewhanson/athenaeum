"""
Tests for the retriever module.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from athenaeum.retriever import query_index, retrieve_context


@pytest.fixture
def mock_index_path(tmp_path):
    # Create fake index directory structure
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "faiss.index").write_text("dummy")
    return index_dir


@patch("athenaeum.retriever.setup_settings")
@patch("athenaeum.retriever.FaissVectorStore.from_persist_path")
@patch("athenaeum.retriever.StorageContext.from_defaults")
@patch("athenaeum.retriever.load_index_from_storage")
def test_query_index(mock_load, mock_context, mock_faiss, mock_setup, mock_index_path):
    # Setup mocks
    mock_query_engine = MagicMock()
    mock_load.return_value.as_query_engine.return_value = mock_query_engine
    
    # Setup response with source nodes
    mock_response = MagicMock()
    mock_response.source_nodes = [
        MagicMock(node=MagicMock(metadata={"source_path": "doc1.txt"}), score=0.9),
        MagicMock(node=MagicMock(metadata={"source_path": "doc2.txt"}), score=0.8)
    ]
    mock_query_engine.query.return_value = mock_response
    
    # Call function
    result = query_index(mock_index_path, "test question")
    
    # Verify setup
    mock_setup.assert_called_once()
    mock_faiss.assert_called_once()
    mock_context.assert_called_once()
    mock_load.assert_called_once()
    mock_load.return_value.as_query_engine.assert_called_once_with(similarity_top_k=5)
    mock_query_engine.query.assert_called_once_with("test question")
    
    # Verify result structure
    assert "answer" in result
    assert "sources" in result
    assert len(result["sources"]) == 2
    assert result["sources"][0]["path"] == "doc1.txt"
    assert result["sources"][0]["score"] == 0.9


@patch("athenaeum.retriever.setup_settings")
@patch("athenaeum.retriever.FaissVectorStore.from_persist_path")
@patch("athenaeum.retriever.StorageContext.from_defaults")
@patch("athenaeum.retriever.load_index_from_storage")
def test_retrieve_context(mock_load, mock_context, mock_faiss, mock_setup, mock_index_path):
    # Setup mocks
    mock_retriever = MagicMock()
    mock_load.return_value.as_retriever.return_value = mock_retriever
    
    # Setup nodes
    node1 = MagicMock()
    node1.get_content.return_value = "content1"
    node1.metadata = {"source_path": "doc1.txt"}
    node1.score = 0.9
    
    node2 = MagicMock()
    node2.get_content.return_value = "content2"
    node2.metadata = {"source_path": "doc2.txt"}
    node2.score = 0.8
    
    mock_retriever.retrieve.return_value = [node1, node2]
    
    # Call function
    result = retrieve_context(mock_index_path, "test question", top_k=2)
    
    # Verify setup
    mock_setup.assert_called_once()
    mock_faiss.assert_called_once()
    mock_context.assert_called_once()
    mock_load.assert_called_once()
    mock_load.return_value.as_retriever.assert_called_once_with(similarity_top_k=2)
    mock_retriever.retrieve.assert_called_once_with("test question")
    
    # Verify result structure
    assert len(result) == 2
    assert result[0]["content"] == "content1"
    assert result[0]["metadata"]["path"] == "doc1.txt"
    assert result[0]["metadata"]["score"] == 0.9
