"""
Tests for the MCP server module.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from athenaeum.mcp_server import app, get_index_dir


@pytest.fixture
def mock_index_dir(tmp_path):
    # Create fake index directory
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "faiss.index").write_text("dummy")
    return index_dir


@pytest.fixture
def client():
    # Create a test client for FastAPI
    return TestClient(app)


@patch("athenaeum.mcp_server.get_index_dir")
def test_health_check(mock_dir, client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("athenaeum.mcp_server.get_index_dir")
def test_list_models(mock_dir, client):
    response = client.get("/models")
    assert response.status_code == 200
    assert response.json()["object"] == "list"
    assert len(response.json()["data"]) > 0
    assert response.json()["data"][0]["id"] == "athenaeum-index-retrieval"


@patch("athenaeum.mcp_server.get_index_dir")
@patch("athenaeum.mcp_server.retrieve_context")
def test_mcp_retrieve(mock_retrieve, mock_dir, client, mock_index_dir):
    # Setup mock
    mock_dir.return_value = mock_index_dir
    mock_retrieve.return_value = [
        {
            "content": "test content",
            "metadata": {
                "path": "doc1.txt",
                "score": 0.9
            }
        }
    ]
    
    # Test endpoint
    response = client.post("/retrieve", json={"query": "test", "limit": 1})
    assert response.status_code == 200
    result = response.json()
    
    # Verify structure
    assert result["object"] == "list"
    assert len(result["data"]) == 1
    assert result["data"][0]["id"] == "doc1.txt"
    assert result["data"][0]["content"] == "test content"
    assert result["model"] == "athenaeum-index-retrieval"


@patch("athenaeum.mcp_server.get_index_dir")
@patch("athenaeum.mcp_server.query_index")
def test_mcp_chat(mock_query, mock_dir, client, mock_index_dir):
    # Setup mock
    mock_dir.return_value = mock_index_dir
    mock_query.return_value = {
        "answer": "test answer",
        "sources": [{"path": "doc1.txt", "score": 0.9}]
    }
    
    # Test endpoint
    response = client.post("/chat", json={
        "messages": [{"role": "user", "content": "test question"}],
        "model": "test-model"
    })
    assert response.status_code == 200
    result = response.json()
    
    # Verify structure
    assert result["object"] == "chat.completion"
    assert result["model"] == "test-model"
    assert len(result["choices"]) == 1
    assert result["choices"][0]["message"]["role"] == "assistant"
    assert result["choices"][0]["message"]["content"] == "test answer"


@patch("athenaeum.mcp_server.get_index_dir")
@patch("athenaeum.mcp_server.retrieve_context")
def test_search_endpoint(mock_retrieve, mock_dir, client, mock_index_dir):
    # Setup mock
    mock_dir.return_value = mock_index_dir
    mock_retrieve.return_value = [
        {
            "content": "a very long test content that should be truncated for the snippet",
            "metadata": {
                "path": "doc1.txt",
                "score": 0.9
            }
        }
    ]
    
    # Test endpoint
    response = client.post("/retrieve", json={"query": "test", "limit": 1})
    assert response.status_code == 200
    result = response.json()
    
    # Verify structure
    assert result["object"] == "list"
    assert len(result["data"]) == 1
    assert result["data"][0]["id"] == "doc1.txt"
