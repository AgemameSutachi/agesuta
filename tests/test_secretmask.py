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
    count_masked_in_text,
    count_secrets_in_text,
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


def test_keyed_value_wrapped_in_quotes_is_masked():
    """★★★2026-09-04・実データ突き合わせで発覚: 値が区切りの直後に引用符で
    始まる形（JSON形式のapi_key: "xxx"等）は、値の文字クラスが引用符を
    除外しているため一致すら試みず完全に見逃していた。★これは本番稼働中の
    マスク(138ab24)にも影響する実際の見逃しだった。ダブルクォート・
    シングルクォートの両方、引用符が前後で保たれたまま値だけ隠れることを
    確認する。
    """
    fake = "a" * 45
    for quote in ('"', "'", ""):
        text = f"api_key: {quote}{fake}{quote}"
        assert count_secrets_in_text(text) >= 1, f"見逃している: quote={quote!r}"
        masked = mask_secrets_in_text(text)
        assert fake not in masked, f"値が残っている: quote={quote!r}"
        if quote:
            assert masked.count(quote) == 2, f"引用符が保たれていない: {masked!r}"


def test_keyword_prefixed_by_variable_name_is_masked():
    """★★★★2026-09-04・実データ(quiz-web-app)突き合わせで発覚(本当の主因):
    実データで独立実装との差112件を1件ずつ確認したところ、全件が
    "gemini_api_key: 'xxx'" のように【変数名がキーワードに"_"で連結
    された形】だった。キーワード先頭の`\\b`は「単語構成文字どうしの
    境界なし」を意味し、"_"も単語構成文字のため"gemini_"の直後の
    "api_key"には境界が無く、一致自体が起きていなかった
    （引用符の見逃しとは別の、独立した原因）。★これも本番稼働中の
    マスク(138ab24)に影響する実際の見逃しだった。
    """
    fake = "b" * 45
    for prefixed_keyword in (f"gemini_api_key: {fake}", f"DB_PASSWORD: {fake}"):
        assert (
            count_secrets_in_text(prefixed_keyword) >= 1
        ), f"見逃している: {prefixed_keyword.split(':')[0]}"
        masked = mask_secrets_in_text(prefixed_keyword)
        assert fake not in masked
        assert prefixed_keyword.split(":")[0] in masked, "項目名まで消えている"


def test_url_query_bracket_placeholder_is_not_masked():
    """★★★2026-09-04・事務局(検証役)発見・窓口裁定で修正:
    "?key=[slack_channel]&page=2" のような、値が"["で始まる設定項目名の
    プレースホルダ表記は、"?"の直後という位置条件だけでは除外できず
    誤ってマスクされていた。値が"["で始まるものはマッチさせない。
    """
    text = "?key=[slack_channel]&page=2"
    assert mask_secrets_in_text(text) == text
    assert count_secrets_in_text(text) == 0


def test_bluesky_app_password_is_masked_via_keyword_not_shape():
    """★★★★★2026-09-04・窓口裁定: 接頭辞なし・4文字ハイフン区切り4組の形式
    パターン自体は外した(video hubの実ログでURLスラッグに誤爆・4ファイル238件の
    実在を確認したため)。実使用のBlueskyアプリパスワード(yt2calendar/
    blueskyapi.py)は"password"キーとして渡るため、項目名つきパターンで
    引き続きマスクされることを確認する。
    """
    app_password = "abcd-efgh-ijkl-mnop"
    masked = mask_secrets_in_text(f"APP_PASSWORD = {app_password}")
    assert app_password not in masked


def test_bare_four_by_four_shape_is_no_longer_masked():
    """★★★★★形式だけ(項目名を伴わない4文字ハイフン区切り4組)は、もう
    マスクされない(窓口裁定・上記参照)。★この裁定は「いま見つからなかった」
    であって「存在しない」ではない——将来、値を項目名なしでログへ出す
    コードが書かれれば、この形では拾えなくなる。
    """
    bare = "abcd-efgh-ijkl-mnop"
    text = f"https://example.com/video/12345/some-{bare}-title-slug"
    assert count_secrets_in_text(text) == 0
    assert mask_secrets_in_text(text) == text


def test_normal_text_is_not_broken():
    """マスク対象でない文字列は変わらない"""
    for text in [
        "trGJQS-eeEY を processing で更新/挿入しました。",
        "配信開始: 1/1 ステータス:live 2026/08/14 22:04 -> 2026/08/15 03:55",
        "2026-08-14T13:04:19Z",
        "https://www.youtube.com/watch?v=1-NyiwtlG3Q",
    ]:
        assert mask_secrets_in_text(text) == text, f"壊れた: {text}"


def test_count_secrets_counts_raw_tokens():
    """生のトークンは形式ごとに1件として数える"""
    text = (
        "a: xoxb" + "-1111111111111-2222222222222-abcdefghijklmnopqrstuvwx\n"
        "b: " + "AIza" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r" + "\n"
        "c: normal text with no secret\n"
    )
    assert count_secrets_in_text(text) == 2


def test_count_secrets_does_not_recount_masked_residue():
    """★2026-09-04・窓口指摘（相談役発見）: マスク済みの残骸（接頭辞のみ）を
    生の値として二重に数えない。数えてしまうと「マスクしても検証の一致数が
    0にならない」——正しく動いても永久に通らない検証になる。
    """
    raw = "slack: xoxb" + "-1111111111111-2222222222222-abcdefghijklmnopqrstuvwx"
    assert count_secrets_in_text(raw) == 1

    masked = mask_secrets_in_text(raw)
    assert "xoxb-1" in masked  # 接頭辞は残る設計
    assert (
        count_secrets_in_text(masked) == 0
    ), "マスク済みの残骸を生の値として数えてしまっている"


def test_count_secrets_does_not_recount_masked_value_in_keyed_form():
    """★2026-09-04・実測で発覚した回帰: キー付きパターン(slack_token: xxx)の
    値グループは伏せ字("*")まで含めて捕らえるため、既にマスク済みの値は
    長さだけでは生の値と見分けが付かない（見かけの長さは元の値と同じに
    なるため）。値に"*"を含むものは数えないこと。
    """
    raw = "slack_token: xoxb" + "-1111111111111-2222222222222-abcdefghijklmnopqrstuvwx"
    assert count_secrets_in_text(raw) >= 1

    masked = mask_secrets_in_text(raw)
    assert (
        count_secrets_in_text(masked) == 0
    ), "キー付きパターン経由で残骸を生と誤数している"


def test_count_secrets_is_zero_after_masking_all_pattern_kinds():
    """各パターン種別で、マスク後にcountが0になることを確認する（回帰防止）"""
    samples = [
        "xoxb" + "-3333333333333-4444444444444-zzzzzzzzzzzzzzzzzzzzzzzz",
        "xapp" + "-1-A0000000000-1111111111111-abcdefghijklmnopqrstuvwxyz012345",
        "AIza" + "Q1w2E3r4T5y6U7i8O9p0A1s2D3f4G5h6J7k",
        "sk-" + "abcdefghijklmnopqrstuvwxyz987654",
        "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789",
        "tk_" + "abcdefghijklmnop9999",
    ]
    for raw in samples:
        assert (
            count_secrets_in_text(raw) >= 1
        ), f"生の値が検出できていない: {raw[:10]}..."
        masked = mask_secrets_in_text(raw)
        assert (
            count_secrets_in_text(masked) == 0
        ), f"マスク後も検出された: {raw[:10]}..."


def test_count_masked_distinguishes_raw_from_masked():
    """count_masked_in_text: 生の値は0件・マスク済みの残骸は1件として数える"""
    raw = "xoxb" + "-1111111111111-2222222222222-abcdefghijklmnopqrstuvwx"
    assert count_masked_in_text(raw) == 0, "生の値をマスク済みと誤検出している"

    masked = mask_secrets_in_text(raw)
    assert count_masked_in_text(masked) == 1
    assert count_secrets_in_text(masked) == 0


def test_mask_secrets_in_text_is_idempotent_across_calls():
    """★★★2026-09-04・事務局(検証役)が実測で発見した回帰:
    mask_secrets_in_text()を2回連続で通すと、種別の接頭辞（"xoxb-1"等）
    ごと伏せ字に潰れていた（冪等ではなかった）。原因は1回目の残骸
    （keepぴったりの6文字）が2回目でmask_secret()の「短い値は全部隠す」
    分岐に飲まれたため。既存ログへ繰り返し適用しても壊れないことが必須
    （書き換えは元に戻せない）。
    """
    raw = "slack_token: xoxb" + "-1111111111111-2222222222222-abcdefghijklmnopqrstuvwx"
    once = mask_secrets_in_text(raw)
    twice = mask_secrets_in_text(once)
    assert once == twice, "2回目の適用で結果が変わった（冪等ではない）"
    assert "xoxb-1" in twice, "2回目で種別プレフィックスが消えた"


def test_embedded_asterisk_in_raw_value_is_still_masked():
    """★★★★2026-09-04・窓口裁定（事務局が実測で発見した「穴3」）:
    「値が"*"を含むなら既にマスク済み」という以前の判定は、項目名つき
    パターン（password= / client_secret: 等）には成立しない。そちらの値は
    利用者が決める任意文字列で"*"を普通に含みうる。「マスク済みの形」
    （先頭keep文字以内＋残り全部"*"）で判定し直し、埋め込みの"*"を持つ
    生の値は素通りしないことを確認する。
    """
    samples = [
        "password = Pa*ssw0rd-Long-Enough-Value-123",
        "client_secret: ab*cdefghijklmnopqrstuvwxyz",
    ]
    for text in samples:
        assert (
            count_secrets_in_text(text) >= 1
        ), f"件数0で素通りしている: {text[:15]}..."
        masked = mask_secrets_in_text(text)
        assert masked != text, f"マスクされず素通りしている: {text[:15]}..."


def test_mask_and_count_use_the_same_threshold():
    """★★★2026-09-04・事務局(検証役)が実測で発見した、いちばん重い指摘:
    count_secrets_in_text()とmask_secrets_in_text()の判定基準が
    ずれており、「件数0なのに実際には書き換わる」行があった
    （例: "api_key: なし" のような短い値）。数える対象と書き換わる対象を
    一致させる（_is_raw_candidate()に統一）。
    """
    text = "api_key: なし"
    assert count_secrets_in_text(text) == 0
    assert mask_secrets_in_text(text) == text, "countは0なのにmaskで書き換わっている"


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
