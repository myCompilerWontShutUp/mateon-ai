import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.contest_extraction.extraction import resolve_image_mime_type

_AUTH_HEADERS = {"X-Internal-Secret": get_settings().internal_shared_secret}


@pytest.mark.parametrize(
    ("filename", "expected_mime_type"),
    [("poster.jpg", "image/jpeg"), ("poster.JPEG", "image/jpeg"), ("poster.png", "image/png")],
)
def test_resolve_image_mime_type_accepts_supported_extensions(
    filename: str, expected_mime_type: str
) -> None:
    assert resolve_image_mime_type(filename) == expected_mime_type


@pytest.mark.parametrize("filename", [None, "", "poster", "poster.gif", "poster.pdf"])
def test_resolve_image_mime_type_rejects_unsupported_extensions(filename: str | None) -> None:
    with pytest.raises(Exception):
        resolve_image_mime_type(filename)


async def test_extract_image_rejects_unsupported_extension_over_http(client: AsyncClient) -> None:
    response = await client.post(
        "/contests/extract-image",
        files={"img_file": ("poster.gif", b"fake-bytes", "image/gif")},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 400


async def test_extract_image_rejects_empty_file_over_http(client: AsyncClient) -> None:
    response = await client.post(
        "/contests/extract-image",
        files={"img_file": ("poster.png", b"", "image/png")},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 400
