import logging

from agesuta.slackapi import SlackPoster


def _make_bare_poster(client=None):
    """__init__ を経由せず、必要最小限の属性だけを持つ SlackPoster を作る。"""
    poster = object.__new__(SlackPoster)
    poster.logger = logging.getLogger(__name__)
    poster.channel = "test-channel"
    poster.token = "test-token"
    poster.client = client
    return poster


def test_textpost_empty_text_returns_empty_string():
    poster = _make_bare_poster(client=object())
    assert poster.textpost("") == ""


def test_imagepost_empty_path_returns_empty_string():
    poster = _make_bare_poster(client=object())
    assert poster.imagepost("") == ""


def test_get_channelid_no_client_returns_error():
    poster = _make_bare_poster(client=None)
    ret, channel_id = poster.get_channelid("some-channel")
    assert ret == 1
    assert channel_id == ""


def test_get_channelid_recognizes_channel_id_format():
    poster = _make_bare_poster(client=object())
    ret, channel_id = poster.get_channelid("C1234567890")
    assert ret == 0
    assert channel_id == "C1234567890"


# --- 画像投稿がEXEへフォールバックしたときに本文が失われないこと ---
from unittest.mock import MagicMock, patch

import agesuta.slackapi as slackapi_module


def _make_fallback_poster(upload_side_effect):
    """files_upload_v2 が指定の例外を投げ、EXE・textpost を記録する SlackPoster を作る。"""
    client = MagicMock()
    client.files_upload_v2.side_effect = upload_side_effect
    poster = _make_bare_poster(client=client)
    calls = []
    poster.get_channelid = MagicMock(return_value=(0, "C1234567890"))
    poster.imagepost_exe = MagicMock(
        side_effect=lambda *a, **k: calls.append("image_exe") or "111.1"
    )
    poster.imagepost_from_url_exe = MagicMock(
        side_effect=lambda *a, **k: calls.append("url_exe") or "222.2"
    )
    poster.textpost = MagicMock(
        side_effect=lambda *a, **k: calls.append("text") or "333.3"
    )
    return poster, calls


def _fake_image_response():
    response = MagicMock()
    response.content = b"jpeg-bytes"
    return response


def test_imagepost_from_url_timeout_fallback_also_posts_caption():
    """アップロードがタイムアウトしてEXEへ逃げても、本文を画像の後に投稿する。"""
    poster, calls = _make_fallback_poster(TimeoutError("The read operation timed out"))
    with patch.object(
        slackapi_module.requests, "get", return_value=_fake_image_response()
    ):
        ts = poster.imagepost_from_url("https://example.com/a.jpg", "本文です")
    assert ts == "222.2"
    assert calls == ["url_exe", "text"]
    poster.textpost.assert_called_once_with(
        "本文です", channel="test-channel", token="test-token"
    )


def test_imagepost_fallback_also_posts_caption():
    poster, calls = _make_fallback_poster(TimeoutError("timed out"))
    ts = poster.imagepost("thumb.jpg", "本文です")
    assert ts == "111.1"
    assert calls == ["image_exe", "text"]


def test_fallback_posts_caption_even_if_exe_raises():
    """EXE自体が失敗しても本文だけは届ける。"""
    poster, calls = _make_fallback_poster(TimeoutError("timed out"))
    poster.imagepost_exe = MagicMock(side_effect=OSError("exe not runnable"))
    assert poster.imagepost("thumb.jpg", "本文です") == ""
    poster.textpost.assert_called_once()


def test_fallback_without_caption_posts_no_text():
    poster, calls = _make_fallback_poster(TimeoutError("timed out"))
    poster.imagepost("thumb.jpg")
    assert calls == ["image_exe"]


def test_api_success_does_not_post_caption_separately():
    """API成功時は initial_comment で本文が付くので、別途テキスト投稿しない。"""
    client = MagicMock()
    client.files_upload_v2.return_value = {"files": [{"timestamp": 123}]}
    poster = _make_bare_poster(client=client)
    poster.get_channelid = MagicMock(return_value=(0, "C1234567890"))
    poster.textpost = MagicMock()
    assert poster.imagepost("thumb.jpg", "本文です") == "123"
    poster.textpost.assert_not_called()
