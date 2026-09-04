"""ログへの認証情報マスク（agesuta.secretmask）のユニットテスト。

2026-09-04・ユーザー承認済み（窓口経由・案3の①）。working/yt2calendar/
logmask.py（2026-08-15導入）を持ち上げて共通部品化した際の検証。

★このファイルに実在の値は一切書かない。テスト用の値はすべて連番・
  アルファベット順など、明らかに架空と分かる形にする（過去にGoogle側は
  架空の連番なのにSlack側だけ実在のチームID・ボットIDが入っていた実例が
  あるため、両方とも同じ架空パターンで統一する）。
"""

import logging

import pytest

from agesuta.secretmask import (
    MaskingFormatter,
    install_secret_mask,
    mask_secret,
    mask_secrets_in_text,
)


def test_mask_secret_keeps_head():
    """先頭6文字だけ残してマスクする（末尾ではない・窓口指示どおり）"""
    assert mask_secret("ABCDEFGHIJ") == "ABCDEF****"
    # 短すぎる値は全部隠す
    assert mask_secret("abc") == "***"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""


def test_youtube_api_key_is_masked():
    """YouTube APIキーは形式から検出してマスクする"""
    key = "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r"
    assert len(key) == 39
    masked = mask_secrets_in_text(f"APIキー読み込み:{key}")

    assert key not in masked
    assert masked.startswith("APIキー読み込み:AIzaA1"), "先頭6文字が残っていない"


def test_slack_bot_token_is_masked():
    """Slackボットトークン(xoxb-)は形式から検出してマスクする"""
    token = "xoxb" + "-1111111111111-2222222222222-abcdefghijklmnopqrstuvwx"
    masked = mask_secrets_in_text(f"token issued: {token}")
    assert token not in masked
    assert "xoxb-1" in masked, "先頭の種別プレフィックスが残っていない"


def test_slack_app_token_is_masked():
    """Slackアプリレベルトークン(xapp-)も検出してマスクする（窓口指定）"""
    token = "xapp" + "-1-A0000000000-1111111111111-abcdefghijklmnopqrstuvwxyz012345"
    masked = mask_secrets_in_text(f"connecting with {token}")
    assert token not in masked
    assert "xapp-1" in masked


def test_openai_style_key_is_masked():
    """sk- 形式のキーは十分な長さがあれば検出してマスクする（窓口指定）"""
    key = "sk-" + "abcdefghijklmnopqrstuvwxyz012345"
    masked = mask_secrets_in_text(f"api key: {key}")
    assert key not in masked
    assert "sk-abc" in masked, "先頭6文字が残っていない"


def test_short_sk_prefix_is_not_over_masked():
    """短い 'sk-' を含む語（誤検出しやすい形）は壊さない"""
    text = "sk-test という設定名を使っています"
    assert mask_secrets_in_text(text) == text


def test_github_pat_is_masked():
    """GitHub個人アクセストークン(ghp_)を検出してマスクする（窓口指定）"""
    token = "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789"
    masked = mask_secrets_in_text(f"github_token: {token}")
    assert token not in masked


def test_generic_tk_token_is_masked():
    """汎用トークン接頭辞 tk_ を検出してマスクする（窓口指定）"""
    token = "tk_" + "abcdefghijklmnop0123"
    masked = mask_secrets_in_text(f"value={token}")
    assert token not in masked


def test_keyed_config_values_are_masked():
    """設定ファイル形式(key: value / KEY = value)は項目名を残して値だけ隠す"""
    token = "xoxb" + "-3333333333333-4444444444444-zzzzzzzzzzzzzzzzzzzzzzzz"
    masked = mask_secrets_in_text(f"slack_token: {token}")
    assert token not in masked
    assert "slack_token:" in masked

    key = "AIza" + "Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4J3i"
    masked = mask_secrets_in_text(f"APP_PASSWORD = {key}")
    assert key not in masked
    assert "APP_PASSWORD" in masked


def test_request_url_key_parameter_is_masked():
    """リクエストURLの key= は項目名を残して値だけ隠す"""
    key = "AIza" + "B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s"
    text = (
        "HttpError 429 when requesting https://example.googleapis.com/v3/"
        f"search?channelId=UCabc&part=snippet&key={key}&alt=json returned"
    )
    masked = mask_secrets_in_text(text)

    assert key not in masked
    assert "key=" in masked, "項目名まで消えている"
    assert "channelId=UCabc" in masked, "無関係なパラメータが壊れている"


def test_bluesky_app_password_is_masked():
    """Blueskyのアプリパスワード形式(4文字x4組)もマスクする"""
    app_password = "abcd-efgh-ijkl-mnop"
    masked = mask_secrets_in_text(f"APP_PASSWORD = {app_password}")
    assert app_password not in masked


def test_normal_text_is_not_broken():
    """マスク対象でない文字列は変わらない"""
    for text in [
        "trGJQS-eeEY を processing で更新/挿入しました。",
        "配信開始: 1/1 ステータス:live 2026/08/14 22:04 -> 2026/08/15 03:55",
        "2026-08-14T13:04:19Z",
        "https://www.youtube.com/watch?v=1-NyiwtlG3Q",
    ]:
        assert mask_secrets_in_text(text) == text, f"壊れた: {text}"


def test_formatter_masks_traceback():
    """Formatterを差し替えると例外のトレースバックもマスクされる"""
    key = "AIza" + "B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s"
    base = logging.Formatter("%(levelname)s %(message)s")
    formatter = MaskingFormatter(base)

    try:
        raise ValueError(f"failed to call https://example.com/v3?key={key}")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="API呼び出しに失敗しました",
            args=(),
            exc_info=sys.exc_info(),
        )

    output = formatter.format(record)
    assert "API呼び出しに失敗しました" in output
    assert "ValueError" in output, "トレースバックが出力されていない"
    assert key not in output, "トレースバック中のキーが漏れている"


def test_install_secret_mask_is_idempotent():
    """二重に適用してもFormatterが多重ラップされない"""
    root = logging.getLogger()
    original = list(root.handlers)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    try:
        install_secret_mask()
        first = handler.formatter
        assert isinstance(first, MaskingFormatter)

        # 2回目は差し替えないこと
        assert install_secret_mask() == 0
        assert handler.formatter is first
    finally:
        root.removeHandler(handler)
        root.handlers = original


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
