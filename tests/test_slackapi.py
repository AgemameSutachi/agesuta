import logging
import ssl
import urllib.error

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
import pytest


@pytest.fixture(autouse=True)
def sleep_mock():
    """再試行の待機を実際には行わず、呼び出しを記録する（全テストで実時間の待機を防ぐ）。"""
    with patch.object(slackapi_module.time, "sleep") as mocked:
        yield mocked


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


# --- 一時的な失敗は数回再試行してから EXE へフォールバックすること ---
import socket
import urllib.error

from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from agesuta.slackapi import is_transient_api_error


def _slack_api_error(error_code, status_code=200, headers=None):
    """指定のエラーコード・HTTP ステータスを持つ SlackApiError を作る。"""
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/files.completeUploadExternal",
        req_args={},
        data={"ok": False, "error": error_code},
        headers=headers or {},
        status_code=status_code,
    )
    return SlackApiError("The request to the Slack API failed.", response)


def _http_error(code, headers=None):
    return urllib.error.HTTPError(
        "https://files.slack.com/upload/v1/xxx", code, "error", headers or {}, None
    )


def _success_response():
    return {"files": [{"timestamp": 123}]}


def test_imagepost_transient_failure_then_success_does_not_fallback(sleep_mock):
    """1回目がタイムアウトでも2回目で成功すれば、EXEも本文の別投稿も行わない。"""
    poster, calls = _make_fallback_poster(
        [TimeoutError("The read operation timed out"), _success_response()]
    )
    assert poster.imagepost("thumb.jpg", "本文です") == "123"
    assert poster.client.files_upload_v2.call_count == 2
    assert calls == []
    poster.imagepost_exe.assert_not_called()
    poster.textpost.assert_not_called()
    sleep_mock.assert_called_once_with(5)


def test_imagepost_transient_failure_persists_then_fallback_with_caption(sleep_mock):
    """一時的な失敗が続けば、規定回数試行した後に EXE へ逃げ、本文も投稿する。"""
    poster, calls = _make_fallback_poster(TimeoutError("timed out"))
    assert poster.imagepost("thumb.jpg", "本文です") == "111.1"
    assert poster.client.files_upload_v2.call_count == 3
    assert calls == ["image_exe", "text"]
    assert [c.args[0] for c in sleep_mock.call_args_list] == [5, 15]


def test_imagepost_from_url_504_persists_then_fallback_with_caption(sleep_mock):
    poster, calls = _make_fallback_poster(_http_error(504))
    with patch.object(
        slackapi_module.requests, "get", return_value=_fake_image_response()
    ) as get_mock:
        ts = poster.imagepost_from_url("https://example.com/a.jpg", "本文です")
    assert ts == "222.2"
    assert poster.client.files_upload_v2.call_count == 3
    assert calls == ["url_exe", "text"]
    # ダウンロードは再試行の対象外
    get_mock.assert_called_once()


def test_imagepost_permanent_error_falls_back_immediately(sleep_mock):
    """invalid_auth のような恒久的な失敗は再試行せず、すぐ EXE へ逃げる。"""
    poster, calls = _make_fallback_poster(_slack_api_error("invalid_auth"))
    assert poster.imagepost("thumb.jpg", "本文です") == "111.1"
    assert poster.client.files_upload_v2.call_count == 1
    assert calls == ["image_exe", "text"]
    sleep_mock.assert_not_called()


def test_imagepost_from_url_recreates_stream_for_each_attempt(sleep_mock):
    """試行ごとに渡されるストリームが毎回画像全体を含む（読み終えた物の使い回しでない）。"""
    received = []

    def fake_upload(**kwargs):
        received.append(kwargs["file"].read())
        if len(received) == 1:
            raise TimeoutError("The read operation timed out")
        return _success_response()

    poster, calls = _make_fallback_poster(fake_upload)
    with patch.object(
        slackapi_module.requests, "get", return_value=_fake_image_response()
    ):
        ts = poster.imagepost_from_url("https://example.com/a.jpg", "本文です")
    assert ts == "123"
    assert received == [b"jpeg-bytes", b"jpeg-bytes"]
    assert calls == []


def test_textpost_transient_failure_then_success_does_not_use_exe(sleep_mock):
    client = MagicMock()
    client.chat_postMessage.side_effect = [
        ConnectionResetError("reset by peer"),
        {"ts": "999.9"},
    ]
    poster = _make_bare_poster(client=client)
    poster.textpost_exe = MagicMock(return_value="000.0")
    assert poster.textpost("こんにちは") == "999.9"
    assert client.chat_postMessage.call_count == 2
    poster.textpost_exe.assert_not_called()
    sleep_mock.assert_called_once_with(5)


def test_retry_settings_can_be_overridden_by_attributes(sleep_mock):
    poster, calls = _make_fallback_poster(TimeoutError("timed out"))
    poster.api_max_attempts = 2
    poster.api_retry_waits = [0.5]
    assert poster.imagepost("thumb.jpg") == "111.1"
    assert poster.client.files_upload_v2.call_count == 2
    sleep_mock.assert_called_once_with(0.5)


def test_retry_after_header_is_respected_and_capped(sleep_mock):
    poster, calls = _make_fallback_poster(
        [
            _slack_api_error("ratelimited", 429, {"Retry-After": "7"}),
            _slack_api_error("ratelimited", 429, {"retry-after": "3600"}),
            _success_response(),
        ]
    )
    assert poster.imagepost("thumb.jpg") == "123"
    assert [c.args[0] for c in sleep_mock.call_args_list] == [7.0, 60]


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("The read operation timed out"),
        socket.timeout("timed out"),
        ConnectionResetError("reset"),
        urllib.error.URLError("temporary failure in name resolution"),
        _http_error(504),
        _http_error(502),
        _http_error(429),
        _slack_api_error("unknown", status_code=504),
        _slack_api_error("ratelimited", status_code=429),
        _slack_api_error("internal_error", status_code=200),
    ],
)
def test_is_transient_api_error_true(exc):
    assert is_transient_api_error(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        _slack_api_error("invalid_auth"),
        _slack_api_error("channel_not_found"),
        _slack_api_error("not_authed", status_code=401),
        _http_error(404),
        urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate verify failed")
        ),
        ValueError("bad value"),
        KeyError("files"),
    ],
)
def test_is_transient_api_error_false(exc):
    assert is_transient_api_error(exc) is False
