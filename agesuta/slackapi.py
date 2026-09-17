from .com import log_decorator
import logging
import re
import ssl
import certifi
from .configmanager import ConfigManager
import inspect

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    HAS_SLACK_SDK = True
except ImportError:
    WebClient = None
    SlackApiError = None
    HAS_SLACK_SDK = False

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False

from io import BytesIO
import http.client
import socket
import subprocess
import os
import time
import urllib.error

# API 呼び出しの再試行の既定値（初回を含む最大試行回数と、各再試行前の待機秒数）
DEFAULT_API_MAX_ATTEMPTS = 3
DEFAULT_API_RETRY_WAITS = (5, 15)
# Retry-After ヘッダを尊重するときの待機秒数の上限（長すぎる停止を防ぐ）
MAX_RETRY_AFTER_SECONDS = 60

# 再試行する HTTP ステータス（429 と 5xx）の判定用
_RATE_LIMIT_STATUS = 429

# 一時的な失敗とみなす Slack API のエラーコード（HTTP 200 で返る場合への備え）
_TRANSIENT_SLACK_ERROR_CODES = frozenset(
    {
        "ratelimited",
        "internal_error",
        "fatal_error",
        "service_unavailable",
        "request_timeout",
    }
)

# 例外の型だけで一時的な失敗と判断できるもの
# （socket.timeout は 3.10 以降 TimeoutError の別名だが、3.9 では別クラスのため併記する）
_TRANSIENT_EXCEPTION_TYPES = (
    TimeoutError,
    socket.timeout,
    ConnectionError,
    http.client.IncompleteRead,
    ssl.SSLEOFError,
)


def _is_retryable_status(status):
    """HTTP ステータスが再試行に値する（429 または 5xx）かを返します。"""
    return isinstance(status, int) and (status == _RATE_LIMIT_STATUS or status >= 500)


def is_transient_api_error(exc):
    """
    Slack API 呼び出しで発生した例外が、再試行に値する一時的な失敗かを判定します。

    再試行する: タイムアウト・接続断・urllib の URLError・HTTP 429/5xx、
    および SlackApiError のうち HTTP ステータスが 429/5xx のもの
    （または ratelimited・internal_error 等の一時的なエラーコード）。
    再試行しない: invalid_auth・channel_not_found などの恒久的な SlackApiError、
    ValueError など、やり直しても結果が変わらない失敗。

    Args:
        exc (BaseException): 判定する例外。

    Returns:
        bool: 一時的な失敗なら True。
    """
    # HTTPError は URLError の派生なので、ステータスで判定するため先に調べる
    if isinstance(exc, urllib.error.HTTPError):
        return _is_retryable_status(exc.code)
    if isinstance(exc, urllib.error.URLError):
        # 証明書検証の失敗は包まれて届くが、やり直しても直らないので再試行しない
        return not isinstance(
            getattr(exc, "reason", None), ssl.SSLCertVerificationError
        )
    if isinstance(exc, _TRANSIENT_EXCEPTION_TYPES):
        return True
    if SlackApiError is not None and isinstance(exc, SlackApiError):
        response = getattr(exc, "response", None)
        if _is_retryable_status(getattr(response, "status_code", None)):
            return True
        error_code = None
        try:
            error_code = response.get("error") if response is not None else None
        except Exception:
            error_code = None
        return error_code in _TRANSIENT_SLACK_ERROR_CODES
    return False


def _retry_after_seconds(exc):
    """
    例外に付随するレスポンスの Retry-After ヘッダ（秒）を返します。無ければ None。

    SlackApiError は response.headers、urllib の HTTPError は headers から読みます。
    値は MAX_RETRY_AFTER_SECONDS を上限に切り詰めます。
    """
    headers = None
    if isinstance(exc, urllib.error.HTTPError):
        headers = exc.headers
    else:
        headers = getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    value = None
    try:
        for key in headers:
            if str(key).lower() == "retry-after":
                value = headers[key]
                break
    except Exception:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


class SlackPoster:
    """
    Slack API および外部実行ファイルを使用してSlackに投稿するクラス。

    初期化時に設定ファイルのパスを指定できます。
    """

    def __init__(
        self,
        slack_api_config_path="./config/slackapi.ini",
        slack_exe_config_path="./config/slackexe.ini",
        config_encoding="cp932",
        logger_instance=logging.getLogger(__name__),
    ):
        """
        SlackPoster クラスを初期化します。

        Args:
            slack_api_config_path (str): Slack API 設定ファイルへのパス。
            slack_exe_config_path (str): Slack 実行ファイル設定ファイルへのパス。
        """
        if not HAS_SLACK_SDK:
            raise ImportError(
                "slack_sdk がインストールされていないため、SlackPoster を初期化できません。"
                "Slack連携機能を使用するには 'pip install agesuta[slack]' を実行して "
                "必要な依存パッケージをインストールしてください。"
            )
        self.logger = logger_instance

        # Slack API 設定の読み込み
        default_api_config_dic = {
            "slack_token": "testtoken",
            "slack_channel": "testchannnel",
        }
        try:
            self.config_slackapi = ConfigManager(
                default_dic=default_api_config_dic,
                config_path=slack_api_config_path,
                encoding=config_encoding,
            )
            self.token = self.config_slackapi.get("slack_token")
            self.channel = self.config_slackapi.get("slack_channel")
            if self.token == "testtoken" or self.channel == "testchannnel":
                self.logger.warning(
                    "Slack API token or channel is using default value. Check config file."
                )
        except Exception as e:
            self.logger.exception(
                f"Failed to load Slack API config from {slack_api_config_path}"
            )
            # 設定ファイル読み込み失敗時のデフォルト値
            self.token = default_api_config_dic["slack_token"]
            self.channel = default_api_config_dic["slack_channel"]

        # Slack 実行ファイル設定の読み込み
        default_exe_config_dic = {
            "slack_textpost_exe_path": ".\\dist\\slack_textpost.exe",
            "slack_imagepost_exe_path": ".\\dist\\slack_imagepost.exe",
            "slack_imagepost_from_url_exe_path": ".\\dist\\slack_imagepost_from_url.exe",
        }
        try:
            self.config_slackexe = ConfigManager(
                default_dic=default_exe_config_dic,
                config_path=slack_exe_config_path,
                encoding="cp932",  # encoding も引数で指定できるようにしても良い
            )
        except Exception as e:
            self.logger.exception(
                f"Failed to load Slack EXE config from {slack_exe_config_path}"
            )
            # 設定ファイル読み込み失敗時のデフォルト値
            # ConfigManagerが内部でデフォルト値を保持していると仮定し、インスタンスは作成しておく
            self.config_slackexe = ConfigManager(
                default_dic=default_exe_config_dic, config_path="", encoding="cp932"
            )

        # Slack WebClient の初期化
        try:
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
            self.client = WebClient(token=self.token, ssl=self.ssl_context)
            self.logger.info("Slack WebClient initialized successfully.")
        except Exception as e:
            self.logger.exception("Failed to initialize Slack WebClient.")
            self.client = None  # クライアント初期化失敗時はNoneとする

    def get_channelid(self, name):
        """
        チャンネル名からチャンネルIDを取得します。
        """
        if not self.client:
            self.logger.error("Slack client is not initialized.")
            return 1, ""

        # name がすでにチャンネルID形式の場合はそのまま返す（API呼び出しを節約）。
        # Slack のチャンネル/グループ/DM ID は C/G/D で始まる大文字英数字。
        # チャンネル名は小文字・ハイフン・アンダースコアのみ許可され大文字を含まないため、
        # 「大文字英数字のみ」で判定すれば名前との誤検知を避けられる。
        if name and re.fullmatch(r"[CGD][A-Z0-9]{8,}", name):
            return 0, name

        try:
            cursor = None
            while True:
                channels = self.client.conversations_list(cursor=cursor, limit=1000)
                if channels["ok"]:
                    for i in channels["channels"]:
                        if i["name"] == name:
                            return 0, i["id"]
                    cursor = channels.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                else:
                    break
            self.logger.warning(f"Channel name not found: {name}")
            return 1, ""
        except Exception as e:
            self.logger.exception(f"{inspect.currentframe().f_code.co_name}で例外発生")
            return 1, ""

    @log_decorator(logging.getLogger(__name__))
    def textpost_exe(self, text, channel=None, token=None):
        """
        外部実行ファイルを使用してテキストを投稿します。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token

        exe_path = self.config_slackexe.get("slack_textpost_exe_path")
        if not os.path.exists(exe_path):
            self.logger.error(f"Text post executable not found: {exe_path}")
            return ""

        cmd_list = [exe_path]
        if text:
            cmd_list.append(text)
        else:
            self.logger.error("Text is empty for textpost_exe.")
            return ""
        if current_channel:
            cmd_list.append(current_channel)
            if current_token:
                cmd_list.append(current_token)

        try:
            result = subprocess.run(cmd_list, encoding="cp932", capture_output=True)
            if result.stdout:
                for line in result.stdout.splitlines():
                    self.logger.debug(f"textpost_exe stdout: {line}")
            timestamp = ""
            if result.stderr:
                for line in result.stderr.splitlines():
                    if line.startswith("timestamp:"):
                        timestamp = line[len("timestamp:") :].strip()
                    else:
                        self.logger.error(f"textpost_exe stderr: {line}")
            if not timestamp and result.returncode != 0:
                self.logger.error(
                    f"textpost_exe failed with return code {result.returncode}"
                )
            return timestamp
        except Exception as e:
            self.logger.exception("Exception occurred during textpost_exe execution")
            return ""

    @log_decorator(logging.getLogger(__name__))
    def imagepost_exe(self, image_path, channel=None, token=None):
        """
        外部実行ファイルを使用して画像を投稿します。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token

        exe_path = self.config_slackexe.get("slack_imagepost_exe_path")
        if not os.path.exists(exe_path):
            self.logger.error(f"Image post executable not found: {exe_path}")
            return ""

        cmd_list = [exe_path]
        if image_path:
            cmd_list.append(image_path)
        else:
            self.logger.error("image_path is empty for imagepost_exe.")
            return ""
        if current_channel:
            cmd_list.append(current_channel)
            if current_token:
                cmd_list.append(current_token)

        try:
            result = subprocess.run(cmd_list, encoding="cp932", capture_output=True)
            if result.stdout:
                for line in result.stdout.splitlines():
                    self.logger.debug(f"imagepost_exe stdout: {line}")
            timestamp = ""
            if result.stderr:
                for line in result.stderr.splitlines():
                    if line.startswith("timestamp:"):
                        timestamp = line[len("timestamp:") :].strip()
                    else:
                        # UserWarning は無視するなど、元のコードのロジックを維持
                        if "UserWarning" not in line:
                            self.logger.error(f"imagepost_exe stderr: {line}")
            if not timestamp and result.returncode != 0:
                self.logger.error(
                    f"imagepost_exe failed with return code {result.returncode}"
                )
            return timestamp
        except Exception as e:
            self.logger.exception("Exception occurred during imagepost_exe execution")
            return ""

    @log_decorator(logging.getLogger(__name__))
    def imagepost_from_url_exe(self, image_url, channel=None, token=None):
        """
        外部実行ファイルを使用してURLから画像を投稿します。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token

        exe_path = self.config_slackexe.get("slack_imagepost_from_url_exe_path")
        if not os.path.exists(exe_path):
            self.logger.error(f"Image post from URL executable not found: {exe_path}")
            return ""

        cmd_list = [exe_path]
        if image_url:
            cmd_list.append(image_url)
        else:
            self.logger.error("image_url is empty for imagepost_from_url_exe.")
            return ""
        if current_channel:
            cmd_list.append(current_channel)
            if current_token:
                cmd_list.append(current_token)

        try:
            result = subprocess.run(cmd_list, encoding="cp932", capture_output=True)
            if result.stdout:
                for line in result.stdout.splitlines():
                    self.logger.debug(f"imagepost_from_url_exe stdout: {line}")
            timestamp = ""
            if result.stderr:
                for line in result.stderr.splitlines():
                    if line.startswith("timestamp:"):
                        timestamp = line[len("timestamp:") :].strip()
                    else:
                        # UserWarning は無視するなど、元のコードのロジックを維持
                        if "UserWarning" not in line:
                            self.logger.error(f"imagepost_from_url_exe stderr: {line}")
            if not timestamp and result.returncode != 0:
                self.logger.error(
                    f"imagepost_from_url_exe failed with return code {result.returncode}"
                )
            return timestamp
        except Exception as e:
            self.logger.exception(
                "Exception occurred during imagepost_from_url_exe execution"
            )
            return ""

    def _call_api_with_retry(self, api_call, description):
        """
        Slack API 呼び出しを、一時的な失敗のときだけ数回やり直して実行します。

        再試行するかは is_transient_api_error で判定し、恒久的な失敗
        （invalid_auth・channel_not_found 等）は即座に例外を送出します。
        試行回数を使い切った場合も最後の例外をそのまま送出するため、呼び出し元は
        従来どおり外部実行ファイルへのフォールバックへ進めます。

        試行回数と待機秒数はインスタンス属性で変更できます。
        - api_max_attempts (int): 初回を含む最大試行回数（既定 3）
        - api_retry_waits (Sequence[float]): n 回目の再試行前の待機秒数（既定 5, 15）。
          再試行回数が要素数を超えた場合は最後の値を使います。
        429 などで Retry-After ヘッダがあれば、その秒数（上限 60 秒）を優先します。

        注意: HTTP 504 などのタイムアウト系の失敗では、Slack 側では実際には投稿が
        成功していることがあります。その場合、再試行によって同じ内容が二重に投稿
        されることがあります（以前から EXE フォールバックでも同じことが起きていました）。

        Args:
            api_call (Callable[[], Any]): 引数なしで API を呼ぶ関数。試行ごとに呼ばれるため、
                ストリーム等の使い捨ての引数はこの中で毎回作り直すこと。
            description (str): ログに出す呼び出し名（例 "files_upload_v2"）。

        Returns:
            Any: api_call の戻り値。
        """
        max_attempts = getattr(self, "api_max_attempts", DEFAULT_API_MAX_ATTEMPTS)
        retry_waits = getattr(self, "api_retry_waits", DEFAULT_API_RETRY_WAITS)
        try:
            max_attempts = max(1, int(max_attempts))
        except (TypeError, ValueError):
            max_attempts = DEFAULT_API_MAX_ATTEMPTS
        retry_waits = list(retry_waits or [])

        for attempt in range(1, max_attempts + 1):
            try:
                return api_call()
            except Exception as e:
                if attempt >= max_attempts or not is_transient_api_error(e):
                    raise
                wait = (
                    retry_waits[min(attempt - 1, len(retry_waits) - 1)]
                    if retry_waits
                    else 0
                )
                retry_after = _retry_after_seconds(e)
                if retry_after is not None:
                    wait = retry_after
                self.logger.warning(
                    f"{description} が一時的な失敗のため再試行します "
                    f"({attempt}/{max_attempts} 回目が失敗: {type(e).__name__}: {e}) "
                    f"- {wait} 秒後に再試行"
                )
                time.sleep(wait)

    @log_decorator(logging.getLogger(__name__))
    def textpost(self, text, channel=None, token=None):
        """
        Slack APIを使用してテキストメッセージを投稿します。
        API失敗時は外部実行ファイルにフォールバックします。
        タイムアウトや HTTP 429/5xx などの一時的な失敗は、フォールバック前に
        数回再試行します（詳細は _call_api_with_retry を参照）。
        504 等では Slack 側で実は投稿が成功していることがあり、再試行により
        二重投稿になることがあります。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token
        self.logger.info(f"textpost start to channel: {current_channel}")

        if text == "":
            self.logger.error("メッセージが空です。")
            return ""

        # 指定されたトークンやチャンネルがインスタンスのデフォルトと異なる場合は、一時的なクライアントを使用
        use_temp_client = (current_token != self.token) or (
            channel is not None and channel != self.channel
        )  # channelの場合はclient再生成は不要だが、一貫性のためチェック
        client_to_use = (
            WebClient(token=current_token, ssl=self.ssl_context)
            if use_temp_client
            else self.client
        )

        if not client_to_use:
            self.logger.error("Slack client is not initialized or token is invalid.")
            # クライアント初期化失敗時はEXEにフォールバック
            self.logger.info("Attempting textpost using external executable...")
            try:
                timestamp = self.textpost_exe(
                    text, channel=current_channel, token=current_token
                )
                return timestamp
            except Exception as e:
                self.logger.exception(
                    "textpost_exeで例外発生 (Slack client is not initialized)"
                )
                return ""

        try:
            # Call the chat.postMessage method using the WebClient
            # 一時的な失敗（タイムアウト・5xx 等）は数回やり直してからフォールバックする
            result = self._call_api_with_retry(
                lambda: client_to_use.chat_postMessage(
                    channel=current_channel,
                    text=text,
                ),
                "chat_postMessage",
            )
            timestamp = result["ts"]
            self.logger.info(f"message posted successfully. Timestamp: {timestamp}")
            return timestamp

        except Exception as e:
            # API呼び出し失敗時は外部実行ファイルにフォールバック
            self.logger.exception(
                f"{inspect.currentframe().f_code.co_name}で例外発生 - Attempting fallback to executable..."
            )
            try:
                timestamp = self.textpost_exe(
                    text, channel=current_channel, token=current_token
                )
                return timestamp
            except Exception as e:
                self.logger.exception("textpost_exeで例外発生 (Fallback failed)")
                return ""

    def _image_exe_with_caption(self, exe_func, target, caption, channel, token):
        """
        画像投稿を外部実行ファイルで行い、続けて本文(caption)をテキストで投稿します。

        外部実行ファイルは本文を受け取れないため、API失敗時にそのままフォールバック
        すると画像だけが投稿され本文が失われます。これを防ぐため、画像投稿の成否に
        かかわらず本文を textpost(API失敗時は textpost_exe)で別途投稿します。
        """
        try:
            return exe_func(target, channel=channel, token=token)
        finally:
            if caption:
                self.logger.info(
                    "画像投稿をEXEへフォールバックしたため本文を別途投稿します。"
                )
                try:
                    self.textpost(caption, channel=channel, token=token)
                except Exception:
                    self.logger.exception("フォールバック時の本文投稿で例外発生")

    @log_decorator(logging.getLogger(__name__))
    def imagepost(self, image_path, caption="", channel=None, token=None):
        """
        Slack APIを使用して画像を投稿します。
        API失敗時は外部実行ファイルにフォールバックします。
        タイムアウトや HTTP 429/5xx などの一時的な失敗は、フォールバック前に
        数回再試行します（詳細は _call_api_with_retry を参照）。
        504 等では Slack 側で実は投稿が成功していることがあり、再試行により
        二重投稿になることがあります。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token
        self.logger.info(
            f"imagepost start to channel: {current_channel} from path: {image_path}"
        )

        if image_path == "":
            self.logger.error("image_pathが空です。")
            return ""

        use_temp_client = (current_token != self.token) or (
            channel is not None and channel != self.channel
        )
        client_to_use = (
            WebClient(token=current_token, ssl=self.ssl_context)
            if use_temp_client
            else self.client
        )

        if not client_to_use:
            self.logger.error("Slack client is not initialized or token is invalid.")
            # クライアント初期化失敗時はEXEにフォールバック
            self.logger.info("Attempting imagepost using external executable...")
            try:
                timestamp = self._image_exe_with_caption(
                    self.imagepost_exe,
                    image_path,
                    caption,
                    current_channel,
                    current_token,
                )
                return timestamp
            except Exception as e:
                self.logger.exception(
                    "Error posting image for exe (Slack client is not initialized)"
                )
                return ""

        try:
            # Upload image file to Slack
            # APIでチャンネルIDが必要なため、名前からIDを取得
            ret, channel_id = self.get_channelid(current_channel)
            if ret:
                self.logger.error("チャンネル名が見つかりません:" + current_channel)
                # チャンネルID取得失敗時はEXEにフォールバック
                self.logger.info(
                    "Attempting imagepost using external executable (Channel ID not found)..."
                )
                try:
                    timestamp = self._image_exe_with_caption(
                        self.imagepost_exe,
                        image_path,
                        caption,
                        current_channel,
                        current_token,
                    )
                    return timestamp
                except Exception as e:
                    self.logger.exception(
                        "Error posting image for exe (Channel ID not found fallback failed)"
                    )
                    return ""

            # 一時的な失敗（タイムアウト・5xx 等）は数回やり直してからフォールバックする
            response = self._call_api_with_retry(
                lambda: client_to_use.files_upload_v2(
                    channel=channel_id, file=image_path, initial_comment=caption
                ),
                "files_upload_v2",
            )
            timestamp = ""
            if response["files"]:
                timestamp = str(response["files"][0]["timestamp"])
            else:
                self.logger.error(
                    "Image upload response did not contain file information."
                )
                return ""

            self.logger.info(f"Image posted successfully. Timestamp: {timestamp}")
            return timestamp

        except Exception as e:
            # API呼び出し失敗時は外部実行ファイルにフォールバック
            self.logger.exception(
                "Error posting image - Attempting fallback to executable..."
            )
            try:
                timestamp = self._image_exe_with_caption(
                    self.imagepost_exe,
                    image_path,
                    caption,
                    current_channel,
                    current_token,
                )
                return timestamp
            except Exception as e:
                self.logger.exception("Error posting image for exe (Fallback failed)")
                return ""

    @log_decorator(logging.getLogger(__name__))
    def imagepost_from_url(self, image_url, caption="", channel=None, token=None):
        """
        Slack APIを使用してURLから画像を投稿します。
        API失敗時は外部実行ファイルにフォールバックします。
        タイムアウトや HTTP 429/5xx などの一時的な失敗は、フォールバック前に
        数回再試行します（詳細は _call_api_with_retry を参照）。
        504 等では Slack 側で実は投稿が成功していることがあり、再試行により
        二重投稿になることがあります。
        """
        if not HAS_REQUESTS:
            raise ImportError(
                "requests がインストールされていないため、URLからの画像投稿機能は使用できません。"
                "この機能を使用するには 'pip install agesuta[slack]' を実行してください。"
            )
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token
        self.logger.info(
            f"imagepost_from_url start to channel: {current_channel} from url: {image_url}"
        )

        if image_url == "":
            self.logger.error("image_urlが空です。")
            return ""

        use_temp_client = (current_token != self.token) or (
            channel is not None and channel != self.channel
        )
        client_to_use = (
            WebClient(token=current_token, ssl=self.ssl_context)
            if use_temp_client
            else self.client
        )

        if not client_to_use:
            self.logger.error("Slack client is not initialized or token is invalid.")
            # クライアント初期化失敗時はEXEにフォールバック
            self.logger.info(
                "Attempting imagepost_from_url using external executable..."
            )
            try:
                timestamp = self._image_exe_with_caption(
                    self.imagepost_from_url_exe,
                    image_url,
                    caption,
                    current_channel,
                    current_token,
                )
                return timestamp
            except Exception as e:
                self.logger.exception(
                    "Error posting image from url for exe (Slack client is not initialized)"
                )
                return ""

        try:
            # Download the image from the URL
            response = requests.get(image_url)
            response.raise_for_status()  # HTTPエラーがあれば例外発生
            thumbnail_binary = response.content

            # Upload image file to Slack
            # APIでチャンネルIDが必要なため、名前からIDを取得
            ret, channel_id = self.get_channelid(current_channel)
            if ret:
                self.logger.error("チャンネル名が見つかりません:" + current_channel)
                # チャンネルID取得失敗時はEXEにフォールバック
                self.logger.info(
                    "Attempting imagepost_from_url using external executable (Channel ID not found)..."
                )
                try:
                    timestamp = self._image_exe_with_caption(
                        self.imagepost_from_url_exe,
                        image_url,
                        caption,
                        current_channel,
                        current_token,
                    )
                    return timestamp
                except Exception as e:
                    self.logger.exception(
                        "Error posting image from url for exe (Channel ID not found fallback failed)"
                    )
                    return ""

            # 画像のダウンロードは再試行せず、アップロードだけを再試行する。
            # 読み終えたストリームを再利用すると空ファイルになるため、BytesIO は
            # 試行ごとに作り直す（lambda の中で生成する）。
            response = self._call_api_with_retry(
                lambda: client_to_use.files_upload_v2(
                    channel=channel_id,
                    file=BytesIO(thumbnail_binary),
                    initial_comment=caption,
                ),
                "files_upload_v2",
            )
            timestamp = ""
            if response["files"]:
                timestamp = str(response["files"][0]["timestamp"])
            else:
                self.logger.error(
                    "Image upload from url response did not contain file information."
                )
                return ""

            self.logger.info(f"Image posted successfully. Timestamp: {timestamp}")
            return timestamp

        except Exception as e:
            # API呼び出し失敗時は外部実行ファイルにフォールバック
            self.logger.exception(
                "Error posting image from url - Attempting fallback to executable..."
            )
            try:
                timestamp = self._image_exe_with_caption(
                    self.imagepost_from_url_exe,
                    image_url,
                    caption,
                    current_channel,
                    current_token,
                )
                return timestamp
            except Exception as e:
                self.logger.exception(
                    "Error posting image from url for exe (Fallback failed)"
                )
                return ""


# --- モジュールを直接実行した場合のテストコード ---
# 通常、この部分はモジュールを使用する側のコードに相当します。
# logging 設定はここで行う例を示しています。
if __name__ == "__main__":
    # ログ設定の例
    # CustomLoggerを使用する場合は、ここでCustomLoggerを初期化します
    # 例: Cl_logger=CustomLogger(...)
    # Cl_logger.log_main()
    # あるいは、basicConfigで簡単な設定を行う
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Script started.")

    # デフォルトの設定ファイルパスでインスタンスを作成
    logger.info("Creating SlackPoster instance with default config paths...")
    poster_default = SlackPoster()
    logger.info(
        f"Default Token: {poster_default.token}, Default Channel: {poster_default.channel}"
    )

    # テキスト投稿の例 (デフォルト設定を使用)
    # timestamp = poster_default.textpost("こんにちは、Slack!")
    # if timestamp:
    #     logger.info(f"Posted text with timestamp: {timestamp}")
    # else:
    #     logger.error("Failed to post text.")

    # 画像投稿の例 (デフォルト設定を使用) - 要実際の画像パス
    # timestamp = poster_default.imagepost("./test_image.png", caption="テスト画像")
    # if timestamp:
    #      logger.info(f"Posted image with timestamp: {timestamp}")
    # else:
    #      logger.error("Failed to post image.")

    # URLからの画像投稿の例 (デフォルト設定を使用) - 要実際のURL
    # timestamp = poster_default.imagepost_from_url("https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png", caption="Google Logo")
    # if timestamp:
    #      logger.info(f"Posted image from URL with timestamp: {timestamp}")
    # else:
    #      logger.error("Failed to post image from URL.")

    # 別の設定ファイルパスを指定してインスタンスを作成する例
    # 実際には './config/alternate_slackapi.ini' と './config/alternate_slackexe.ini'
    # に対応する設定ファイルを作成しておく必要があります。
    alternate_api_config = "./config/alternate_slackapi.ini"
    alternate_exe_config = "./config/alternate_slackexe.ini"

    # ダミーの設定ファイルを作成 (テスト用)
    # if not os.path.exists("./config"):
    #     os.makedirs("./config")
    # with open(alternate_api_config, "w", encoding="cp932") as f:
    #     f.write("[DEFAULT]\n")
    #     f.write("slack_token = alternate_testtoken\n")
    #     f.write("slack_channel = alternate_testchannel\n")
    # with open(alternate_exe_config, "w", encoding="cp932") as f:
    #      f.write("[DEFAULT]\n")
    #      f.write("slack_textpost_exe_path = .\\dist\\alternate_textpost.exe\n")
    #      f.write("slack_imagepost_exe_path = .\\dist\\alternate_imagepost.exe\n")
    #      f.write("slack_imagepost_from_url_exe_path = .\\dist\\alternate_imagepost_from_url.exe\n")

    logger.info(
        f"Creating SlackPoster instance with alternate config paths: {alternate_api_config}, {alternate_exe_config}..."
    )
    try:
        poster_alternate = SlackPoster(
            slack_api_config_path=alternate_api_config,
            slack_exe_config_path=alternate_exe_config,
        )
        logger.info(
            f"Alternate Token: {poster_alternate.token}, Alternate Channel: {poster_alternate.channel}"
        )

        # 別の設定でテキスト投稿の例
        # timestamp = poster_alternate.textpost("これは別の設定からの投稿です。")
        # if timestamp:
        #     logger.info(f"Posted text with alternate settings, timestamp: {timestamp}")
        # else:
        #     logger.error("Failed to post text with alternate settings.")

    except Exception as e:
        logger.exception(
            "Failed to create SlackPoster instance with alternate configs."
        )

    logger.info("Script finished.")
