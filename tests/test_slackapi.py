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