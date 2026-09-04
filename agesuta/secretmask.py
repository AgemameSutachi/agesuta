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
    # ★★★2026-09-04・事務局(検証役)の実測で発覚: "?"/"&"の直後という位置の
    #   条件だけでは、"?key=[slack_channel]&page=2"のような【値が"["で
    #   始まる設定名の表示】まで一致してしまい、コメントが述べる意図
    #   （設定項目名の表示は潰さない）と実装がずれていた。値の文字クラスに
    #   "["も除外に加え、角括弧で始まる値（＝プレースホルダ表記）を
    #   そもそもマッチさせない（窓口裁定）。
    re.compile(
        r"(?i)([?&](?:key|api_key|apikey|access_token|refresh_token|token)=)"
        r"([^&\s\"'\[\)\]}]+)"
    ),
    # 設定ファイルから読み込んだ値の出力 (slack_token: xxx / APP_PASSWORD = xxx /
    # JSON形式の api_key: "xxx" も含む)。
    # ★★★2026-09-04・実データ(mainpc)の突き合わせで発覚(1点目): 値が区切り記号の
    #   直後に引用符で始まる形（例: api_key: "xxx"）だと、値の文字クラスが
    #   引用符を除外しているため【一致すら試みず完全に見逃していた】。
    #   区切りのあとの引用符1個だけを任意（省略可）で拾う専用の組にし、
    #   出力側では前置き（キー名＋区切り＋引用符）として温存する
    #   （mask_secrets_in_text()の"".join(m.groups()[:-1])がそのまま使える）。
    # ★★★★2026-09-04・実データ(quiz-web-app)の突き合わせで発覚(2点目・
    #   本当の主因): 独立実装との差112件を1件ずつ確認したところ、全件が
    #   "gemini_api_key" のような【変数名がキーワードに"_"で連結された形】
    #   だった。キーワード先頭の`\b`は正規表現上「単語構成文字どうしの
    #   境界なし」を意味し、"_"も単語構成文字のため、"gemini_" の直後の
    #   "api_key" には境界が無く一致自体が起きない
    #   （実測: 直前1文字を集計すると112件すべてが"_"）。
    #   ★これは本番稼働中のマスク(commit 138ab24)にも影響する実際の見逃し
    #   （変数名にプロバイダ名等を前置きする命名は他プロジェクトにも
    #   ありうる）。
    #   → キーワード直前の境界条件を、英数字（A-Za-z0-9）が直前に無ければ
    #   一致してよい形に緩め（"_"の直前は許可）、誤検出は従来どおり
    #   文字（アルファベット）が直前にある場合だけ防ぐ。
    re.compile(
        r"(?i)(?<![A-Za-z0-9])(slack_token|slack_app_token|app_password|client_secret|"
        r"api_key|apikey|openai_api_key|github_token|password)"
        r"(\s*[=:]\s*)([\"']?)([^\s,;\"'\)\]}]+)"
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
]
# ★★★★★2026-09-04・窓口裁定によりBluesky形式(4文字ハイフン区切り4組)の
#   接頭辞なしパターンを外した(実データでvideo hub=r_video_refineryのURL
#   スラッグに誤爆・4ファイルで238件の実在を確認。誤検出は【戻せない書き換え】
#   で秘密でない情報を永久に消すため、率ではなく非対称でこちら側に倒した)。
#   実使用のBlueskyアプリパスワード(yt2calendar/blueskyapi.py: APP_PASSWORD)は
#   "password"キーとして渡るため、上の項目名つきパターンで引き続き拾える
#   (コード読解で確認: 値を保持・出力する箇所は無く、例外処理も
#   capture_locals既定Falseでローカル変数を含まない)。
#   ★★★ただし【この裁定は「いま見つからなかった」であって「存在しない」ではない】。
#   将来、APP_PASSWORDの値を項目名なしでログへ出すコードが書かれれば、
#   このパターンでは拾えなくなる。その場合は接頭辞なし・項目名なしの値を
#   拾う専用の設計が別途必要になる。
# 上のリストのうち、先頭から数えて「値だけを隠す」パターンの個数
_KEYED_PATTERN_COUNT = 2
# マスクせずに残す先頭の文字数（トークン種別の接頭辞が読める程度に残す）
_SECRET_KEEP_CHARS = 6


# ★★★2026-09-04・事務局(検証役)が実測で発見: 2回連続でmask_secrets_in_text()
#   を通すと、種別の接頭辞（"xoxb-1"等）ごと伏せ字に潰れる（冪等ではない）。
#   原因: 1回目のマスク後の残骸「xoxb-1」（6文字＝keepぴったり）が2回目の
#   標準パターンに再一致し、mask_secret()の`len(text)<=keep`分岐が
#   「短い値は全部隠す」を適用してしまう（残骸を新しい生の短い値と
#   区別できない）。
_MIN_RAW_LENGTH = 13

# ★★★★2026-09-04・窓口裁定（事務局が実測で発見した「穴3」）: 上の対策で
#   「値が"*"を含むなら既にマスク済み」としたが、それは【形式パターン】
#   にしか成立しない。項目名つきパターン（password= / client_secret: 等）の
#   値は利用者が決める任意文字列で、"*"を普通に含む
#   （実測: "password = Pa*ssw0rd-Long-Enough-Value-123" が件数0・素通り）。
#   → 「"*"を含むか」ではなく【mask_secret()の出力そのものの形】で判定する:
#   非"*"の先頭が_SECRET_KEEP_CHARS文字以内で、そのあとが"*"の連続のみ。
#   これなら埋め込みの"*"を持つ生の値（例の"Pa*ssw0rd..."）は
#   非"*"部分が6文字を超えるため「マスク済み」と誤認しない。
_ALREADY_MASKED_RE = re.compile(r"^[^*]{0,%d}\*+$" % _SECRET_KEEP_CHARS)


def _looks_already_masked(value: str) -> bool:
    """mask_secret()の出力と同じ形（先頭keep文字以内＋残り全部"*"）かを見る。"""
    return bool(_ALREADY_MASKED_RE.match(value or ""))


def mask_secret(value, keep: int = _SECRET_KEEP_CHARS) -> str:
    """APIキーやトークンをログへ出すためにマスクする。先頭keep文字だけ残す。

    ★値が既にmask_secret()の出力の形（先頭keep文字以内＋残り全部"*"）を
    しているなら、他の処理で既にマスク済みとみなしてそのまま返す
    （冪等性の担保）。「"*"を含むか」では判定しない——項目名つきパターンの
    値は利用者が決める任意文字列で"*"を普通に含みうる（窓口裁定・
    事務局実測「穴3」）。
    """
    if value is None:
        return ""
    text = str(value)
    if _looks_already_masked(text):
        return text
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + "*" * (len(text) - keep)


def _is_raw_candidate(value: str) -> bool:
    """まだ伏せられていない「生の値」らしいかを判定する（数える側・隠す側で共通）。

    ★★★2026-09-04・事務局(検証役)が実測で発見した、いちばん重い指摘:
      count_secrets_in_text()は長さで絞っているのに、mask_secrets_in_text()
      は絞っておらず、判定基準が2箇所でずれていた。「件数0なのに書き換わる」
      （例: "api_key: なし" → count=0だがmaskすると書き換わっていた）という、
      数える対象と書き換える対象が一致しない状態を生んでいた。
      → 判定をこの1関数へ集約し、両方から呼ぶ（2箇所に持たない）。
    ★★★★「既にマスク済みか」は_looks_already_masked()（形での判定）を使う。
      "*"を含むかどうかでは判定しない（上のmask_secret()と同じ理由）。
    """
    return (
        bool(value)
        and len(value) > _MIN_RAW_LENGTH
        and not _looks_already_masked(value)
    )


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
    ★★★_is_raw_candidate()を満たさない一致（短すぎる・既に伏せ字を含む）は
      置き換えない。count_secrets_in_text()と同じ判定を使うことで、
      「数えた値」と「書き換わる値」を一致させる（事務局指摘）。
    """
    if not text:
        return text
    result = str(text)
    # 形式から判別できるものを先に一致箇所ごと置き換える
    for pattern in _SECRET_PATTERNS[_KEYED_PATTERN_COUNT:]:
        result = pattern.sub(
            lambda m: (
                mask_secret(m.group(0)) if _is_raw_candidate(m.group(0)) else m.group(0)
            ),
            result,
        )
    # 項目名付きのものは、どの項目かが分かるよう値の部分だけを置き換える
    # （形式パターンで既に隠れている値には冪等に働く）
    for pattern in _SECRET_PATTERNS[:_KEYED_PATTERN_COUNT]:
        result = pattern.sub(
            lambda m: (
                "".join(m.groups()[:-1]) + mask_secret(m.groups()[-1])
                if _is_raw_candidate(m.groups()[-1])
                else m.group(0)
            ),
            result,
        )
    return result


def count_secrets_in_text(text: str) -> int:
    """文字列中の、まだ伏せられていない（生の）認証情報形の一致数を数える。

    ★既存ログの走査（既存ログの伏せ字置換・2026-09-04）用。
    mask_secrets_in_text()と同じパターン定義・同じ_is_raw_candidate()判定を
    使い回す（判定基準を2箇所に持たない・事務局指摘で統一した）。
    ★値は返さない・書き換えない。
    ★1つの値がキー付きパターンと形式パターンの両方に一致することがある
    （例: "slack_token: xoxb-..."）。ここでは「まだ生の値が残っている
    箇所の延べ数」を返す（去重はしない）。
    """
    if not text:
        return 0
    count = 0
    for pattern in _SECRET_PATTERNS[_KEYED_PATTERN_COUNT:]:
        for m in pattern.finditer(text):
            if _is_raw_candidate(m.group(0)):
                count += 1
    for pattern in _SECRET_PATTERNS[:_KEYED_PATTERN_COUNT]:
        for m in pattern.finditer(text):
            if _is_raw_candidate(m.groups()[-1]):
                count += 1
    return count


# ★既存ログの走査で「マスク済みのものと、まだ生のものを分けて数える」ため
#   （窓口指摘・2026-09-04）。mask_secret()の出力形（既知の接頭辞＋任意の
#   文字＋1個以上の伏せ字）をそのまま検出する。★count_secrets_in_textとは
#   別の観点（「残骸が実在するか」）を数えるため、意図的に別関数にする
#   （1つの関数に両方の判定を混ぜると、閾値の変更時に両方の意味が
#   同時に変わってしまう）。
_MASKED_RESIDUE_RE = re.compile(
    r"\b(?:AIza|xox[baprs]-|xapp-|sk-|ghp_|tk_)[0-9A-Za-z_\-]*\*+"
)


def count_masked_in_text(text: str) -> int:
    """既にマスク済み（接頭辞＋伏せ字）に見える箇所の数を数える。"""
    if not text:
        return 0
    return len(_MASKED_RESIDUE_RE.findall(text))


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
