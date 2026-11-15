"""Vision MIME validation preserves supported payloads and fails before network I/O."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pdf_framework.embeddings.vision import ImageDescriber
from src.pdf_framework.schemas.images import ImageDescriptionRequest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("image_format", ["jpeg", "png", "gif", "webp", "bmp"])
def test_vision_media_type_boundary(image_format: str, tmp_path: Path) -> None:
    with patch("src.pdf_framework.embeddings.vision.Anthropic") as client_factory:
        create = client_factory.return_value.messages.create
        create.return_value = MagicMock(content=[MagicMock(text="Description")])
        describer = ImageDescriber(api_key="test", cache_enabled=False, cache_dir=tmp_path)
        request = ImageDescriptionRequest(
            image_bytes=b"image-payload",
            image_format=image_format,
            page_number=0,
            prompt="Describe",
        )

        result = describer.describe(request)

    if image_format == "bmp":
        create.assert_not_called()
        assert result.success is False
        assert result.description == "[Image description failed]"
        assert result.error_message == "Unsupported image media type: image/bmp"
    else:
        assert result.success is True
        assert result.description == "Description"
        create.assert_called_once_with(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{image_format}",
                                "data": base64.standard_b64encode(request.image_bytes).decode(
                                    "utf-8"
                                ),
                            },
                        },
                    ],
                }
            ],
        )
