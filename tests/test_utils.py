"""
Tests for the utils module.
"""

from unittest.mock import MagicMock, patch

from athenaeum.utils import setup_settings


def test_setup_settings():
    """Test that setup_settings configures LlamaIndex with MarkdownNodeParser."""
    with (
        patch("athenaeum.utils.Settings"),
        patch("athenaeum.utils.HuggingFaceEmbedding") as mock_embed,
        patch("athenaeum.utils.MarkdownNodeParser") as mock_parser,
    ):
        mock_embed_instance = MagicMock()
        mock_parser_instance = MagicMock()

        mock_embed.return_value = mock_embed_instance
        mock_parser.return_value = mock_parser_instance

        setup_settings("test-model")

        mock_embed.assert_called_once_with(model_name="test-model")
        mock_parser.assert_called_once_with()
