# ログへ出力する認証情報のマスク（共通部品）
#
# 2026-09-04・ユーザー承認済み（窓口経由・案3: マスク＋処分の①）。
# deskmini（公開サーバ）の本番ログ293ファイル・1.83GBに、Slackトークン形が
# 83ファイル・異なり11種類、Google APIキー形が23ファイル・異なり9種類、
# 平文で残っていた（実測）。agesutaは162本のプロジェクトが使う共有ライブラリ
# のため、ここへ入れれば全体に効く。
#
# ★working/yt2calendar/logmask.py（2026-08-15導入・実績あり）を持ち上げた。
#   新規に書かなかった理由: パターンの切り分け（項目名付き/形式のみ）・
#   Formatterへの委譲・冪等な適用、いずれも既に実データで検証済みの設計
#   だったため。書き直すと同じ検証をやり直すことになる。
# ★★ただし1点だけ変えた: マスクで残す側を「末尾」から「先頭」にした。
#   窓口の指示（2026-09-04）「伏せ方は先頭数文字＋伏せ字」に合わせるため。
#   先頭を残すと xoxb- / xapp- / AIza / sk- / ghp_ のようなトークン種別の
#   接頭辞が読めるので、値そのものを明かさずに「どの種類の認証情報で
#   失敗したか」を障害調査で判別できる（末尾を残す設計より調査に向く）。

import logging
import re

# --- ログへ出力する認証情報のマスク ---
# ログは同期フォルダ経由で複製されることもあるため、APIキーやトークンが
# 平文で残らないようにする。誤検出を避けるため、対象は
# 「その形式でしかありえないもの」に限定している。
_SECRET_PATTERNS = [
    # --- 項目名は残して値だけ隠すパターン ---
    # リクエストURLのクエリパラメータ (?key=... / &access_token=...)。
    # 「key=[slack_channel]」のような設定項目名の表示を潰さないよう、? か & の直後に限定する。
    re.compile(
        r"(?i)([?&](?:key|api_key|apikey|access_token|refresh_token|token)=)"
        r"([^&\s\"'\)\]}]+)"
    ),
    # 設定ファイルから読み込んだ値の出力 (slack_token: xxx / APP_PASSWORD = xxx)
    re.compile(
        r"(?i)\b(slack_token|slack_app_token|app_password|client_secret|"
        r"api_key|apikey|openai_api_key|github_token|password)"
        r"(\s*[=:]\s*)([^\s,;\"'\)\]}]+)"
    ),
    # --- 一致した箇所ごと隠すパターン(その形式でしかありえないもの) ---
    # YouTube Data API のキー
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    # Slack のボット/ユーザー/その他トークン (xoxb- xoxp- xoxa- xoxr- xoxs-)
    re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]+"),
    # Slack のアプリレベルトークン (窓口指定・2026-09-04)
    re.compile(r"\bxapp-[0-9A-Za-z\-]+"),
    # OpenAI形式のシークレットキー (窓口指定)。"sk-" は短く誤検出しやすいため
    # 英数字20文字以上を要求する（実在のキーは40字前後）。
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    # GitHub の個人アクセストークン (窓口指定・実際の形式は "ghp_" + 英数字36字)
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    # 汎用トークン接頭辞 "tk_" (窓口指定)。接頭辞が短く誤検出しやすいため
    # 英数字16文字以上を要求する。
    re.compile(r"\btk_[A-Za-z0-9]{16,}\b"),
    # Bluesky のアプリパスワード (4文字ずつ4組。日付やUUIDとは形が異なる)
    re.compile(r"\b[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}\b"),
]
# 上のリストのうち、先頭から数えて「値だけを隠す」パターンの個数
_KEYED_PATTERN_COUNT = 2
# マスクせずに残す先頭の文字数（トークン種別の接頭辞が読める程度に残す）
_SECRET_KEEP_CHARS = 6


def mask_secret(value, keep: int = _SECRET_KEEP_CHARS) -> str:
    """APIキーやトークンをログへ出すためにマスクする。先頭keep文字だけ残す。"""
    if value is None:
        return ""
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + "*" * (len(text) - keep)


def mask_secrets_in_text(text: str) -> str:
    """文字列に含まれるAPIキー・トークンをマスクした文字列を返す。

    ★★2026-09-04・実際にCustomLogger経由で発火させて発覚したバグ:
      「先頭を残す」マスク（窓口指定）では、キー付きパターンを先に処理すると
      値が「xoxb-5」＋伏せ字になり、その残った先頭断片（"xoxb-5"）が
      次に走る形式パターン（xox[baprs]-...）に再度一致して、
      すでに短くなった残骸をmask_secret()がもう一段隠してしまう
      （先頭が丸ごと消える）。★末尾を残す設計（yt2calendar）では
      残骸がトークンの形をしていないため、この二重適用は起きなかった。
      → 形式パターンを先に処理する（値そのものを丸ごと隠す）。
      　 キー付きパターンは、その後の残骸に対しては冪等（伏せ字を
      　 伏せ字で置き換えるだけ）になり、形式で判別できない値
      　 （キー名だけが手がかりのもの）はそのままキー付きパターンが拾う。
    """
    if not text:
        return text
    result = str(text)
    # 形式から判別できるものを先に一致箇所ごと置き換える
    for pattern in _SECRET_PATTERNS[_KEYED_PATTERN_COUNT:]:
        result = pattern.sub(lambda m: mask_secret(m.group(0)), result)
    # 項目名付きのものは、どの項目かが分かるよう値の部分だけを置き換える
    # （形式パターンで既に隠れている値には冪等に働く）
    for pattern in _SECRET_PATTERNS[:_KEYED_PATTERN_COUNT]:
        result = pattern.sub(
            lambda m: "".join(m.groups()[:-1]) + mask_secret(m.groups()[-1]), result
        )
    return result


class MaskingFormatter(logging.Formatter):
    """既存のFormatterに委譲し、出力直前に認証情報をマスクするFormatter。

    例外のトレースバック(HttpErrorのメッセージに含まれるリクエストURL等)も
    整形後の文字列に対してマスクするため、ログの経路を問わず漏れない。
    """

    def __init__(self, base_formatter: logging.Formatter = None):
        super().__init__()
        self._base_formatter = base_formatter

    def format(self, record: logging.LogRecord) -> str:
        if self._base_formatter is not None:
            text = self._base_formatter.format(record)
        else:
            text = super().format(record)
        return mask_secrets_in_text(text)


def wrap_formatter(base_formatter: logging.Formatter) -> "MaskingFormatter":
    """既存のFormatterをマスク付きでラップして返す（二重ラップは避ける）。"""
    if isinstance(base_formatter, MaskingFormatter):
        return base_formatter
    return MaskingFormatter(base_formatter)


def install_secret_mask() -> int:
    """ルートロガーの各ハンドラへマスク処理を組み込む。

    agesuta の CustomLogger を使わず素の logging を使っているコード向けの
    後付け経路。CustomLogger.log_main() は内部で自動的に組み込むため、
    通常はこの関数を呼ぶ必要はない。差し替えたハンドラ数を返す。
    """
    count = 0
    for handler in logging.getLogger().handlers:
        if isinstance(handler.formatter, MaskingFormatter):
            continue  # 二重適用を防ぐ
        handler.setFormatter(wrap_formatter(handler.formatter))
        count += 1
    return count
