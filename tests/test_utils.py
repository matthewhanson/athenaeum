"""
Tests for the utils module.
"""

import pytest
from unittest.mock import patch, MagicMock
from athenaeum.utils import setup_settings


def test_setup_settings():
    """Test that setup_settings configures LlamaIndex with MarkdownNodeParser."""
    with patch("athenaeum.utils.Settings") as mock_settings:
        with patch("athenaeum.utils.HuggingFaceEmbedding") as mock_embed:
            with patch("athenaeum.utils.OpenAI") as mock_llm:
                with patch("athenaeum.utils.MarkdownNodeParser") as mock_parser:
                    mock_embed_instance = MagicMock()
                    mock_llm_instance = MagicMock()
                    mock_parser_instance = MagicMock()
                    
                    mock_embed.return_value = mock_embed_instance
                    mock_llm.return_value = mock_llm_instance
                    mock_parser.return_value = mock_parser_instance
                    
                    setup_settings("test-model", 1024, 200)
                    
                    mock_embed.assert_called_once_with(model_name="test-model")
                    mock_llm.assert_called_once()
                    mock_parser.assert_called_once_with(chunk_size=1024, chunk_overlap=200)
