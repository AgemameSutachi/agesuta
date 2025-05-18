from .com import log_decorator, CustomLogger
import logging
import ssl
import certifi
from .configmanager import ConfigManager
import inspect
from traceback import TracebackException as TE
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
from io import BytesIO
import subprocess
import os
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
        logger_instance = logging.getLogger(__name__),
    ):
        """
        SlackPoster クラスを初期化します。

        Args:
            slack_api_config_path (str): Slack API 設定ファイルへのパス。
            slack_exe_config_path (str): Slack 実行ファイル設定ファイルへのパス。
        """
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
                self.logger.warning("Slack API token or channel is using default value. Check config file.")
        except Exception as e:
            self.logger.exception(f"Failed to load Slack API config from {slack_api_config_path}")
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
                encoding="cp932", # encoding も引数で指定できるようにしても良い
            )
        except Exception as e:
            self.logger.exception(f"Failed to load Slack EXE config from {slack_exe_config_path}")
            # 設定ファイル読み込み失敗時のデフォルト値
            # ConfigManagerが内部でデフォルト値を保持していると仮定し、インスタンスは作成しておく
            self.config_slackexe = ConfigManager(default_dic=default_exe_config_dic, config_path="", encoding="cp932")


        # Slack WebClient の初期化
        try:
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
            self.client = WebClient(token=self.token, ssl=self.ssl_context)
            self.logger.info("Slack WebClient initialized successfully.")
        except Exception as e:
            self.logger.exception("Failed to initialize Slack WebClient.")
            self.client = None # クライアント初期化失敗時はNoneとする


    def get_channelid(self, name):
        """
        チャンネル名からチャンネルIDを取得します。
        """
        if not self.client:
            self.logger.error("Slack client is not initialized.")
            return 1, ""
        try:
            channels = self.client.conversations_list()
            if channels["ok"]:
                for i in channels["channels"]:
                    if i["name"] == name:
                        return 0, i["id"]
            self.logger.warning(f"Channel name not found: {name}")
            return 1, ""
        except Exception as e:
            self.logger.exception(f"{inspect.currentframe().f_code.co_name}で例外発生")
            return 1, ""

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
                        timestamp = line[len("timestamp:"):].strip()
                    else:
                        self.logger.error(f"textpost_exe stderr: {line}")
            if not timestamp and result.returncode != 0:
                self.logger.error(f"textpost_exe failed with return code {result.returncode}")
            return timestamp
        except Exception as e:
            self.logger.exception("Exception occurred during textpost_exe execution")
            return ""


    # @log_decorator # デコレータはクラスメソッドやインスタンスメソッドに適用する場合、調整が必要です
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
                        timestamp = line[len("timestamp:"):].strip()
                    else:
                        # UserWarning は無視するなど、元のコードのロジックを維持
                        if "UserWarning" not in line:
                            self.logger.error(f"imagepost_exe stderr: {line}")
            if not timestamp and result.returncode != 0:
                self.logger.error(f"imagepost_exe failed with return code {result.returncode}")
            return timestamp
        except Exception as e:
            self.logger.exception("Exception occurred during imagepost_exe execution")
            return ""


    # @log_decorator # デコレータはクラスメソッドやインスタンスメソッドに適用する場合、調整が必要です
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
                        timestamp = line[len("timestamp:"):].strip()
                    else:
                        # UserWarning は無視するなど、元のコードのロジックを維持
                        if "UserWarning" not in line:
                            self.logger.error(f"imagepost_from_url_exe stderr: {line}")
            if not timestamp and result.returncode != 0:
                self.logger.error(f"imagepost_from_url_exe failed with return code {result.returncode}")
            return timestamp
        except Exception as e:
            self.logger.exception("Exception occurred during imagepost_from_url_exe execution")
            return ""

    # デコレータ使用するとうまく動かない -> デコレータは削除または調整が必要です
    # @log_decorator
    def textpost(self, text, channel=None, token=None):
        """
        Slack APIを使用してテキストメッセージを投稿します。
        API失敗時は外部実行ファイルにフォールバックします。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token
        self.logger.info(f"textpost start to channel: {current_channel}")

        if text == "":
            self.logger.error("メッセージが空です。")
            return ""

        # 指定されたトークンやチャンネルがインスタンスのデフォルトと異なる場合は、一時的なクライアントを使用
        use_temp_client = (current_token != self.token) or (channel is not None and channel != self.channel) # channelの場合はclient再生成は不要だが、一貫性のためチェック
        client_to_use = WebClient(token=current_token, ssl=self.ssl_context) if use_temp_client else self.client

        if not client_to_use:
            self.logger.error("Slack client is not initialized or token is invalid.")
            # クライアント初期化失敗時はEXEにフォールバック
            self.logger.info("Attempting textpost using external executable...")
            try:
                timestamp = self.textpost_exe(text, channel=current_channel, token=current_token)
                return timestamp
            except Exception as e:
                self.logger.exception("textpost_exeで例外発生 (Slack client is not initialized)")
                return ""


        try:
            # Call the chat.postMessage method using the WebClient
            result = client_to_use.chat_postMessage(
                channel=current_channel,
                text=text,
            )
            timestamp = result["ts"]
            self.logger.info(f"message posted successfully. Timestamp: {timestamp}")
            return timestamp

        except Exception as e:
            # API呼び出し失敗時は外部実行ファイルにフォールバック
            self.logger.exception(f"{inspect.currentframe().f_code.co_name}で例外発生 - Attempting fallback to executable...")
            try:
                timestamp = self.textpost_exe(text, channel=current_channel, token=current_token)
                return timestamp
            except Exception as e:
                self.logger.exception("textpost_exeで例外発生 (Fallback failed)")
                return ""


    # デコレータ使用するとうまく動かない -> デコレータは削除または調整が必要です
    # @log_decorator
    def imagepost(self, image_path, caption="", channel=None, token=None):
        """
        Slack APIを使用して画像を投稿します。
        API失敗時は外部実行ファイルにフォールバックします。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token
        self.logger.info(f"imagepost start to channel: {current_channel} from path: {image_path}")

        if image_path == "":
            self.logger.error("image_pathが空です。")
            return ""

        use_temp_client = (current_token != self.token) or (channel is not None and channel != self.channel)
        client_to_use = WebClient(token=current_token, ssl=self.ssl_context) if use_temp_client else self.client

        if not client_to_use:
            self.logger.error("Slack client is not initialized or token is invalid.")
            # クライアント初期化失敗時はEXEにフォールバック
            self.logger.info("Attempting imagepost using external executable...")
            try:
                timestamp = self.imagepost_exe(image_path, channel=current_channel, token=current_token)
                return timestamp
            except Exception as e:
                self.logger.exception("Error posting image for exe (Slack client is not initialized)")
                return ""


        try:
            # Upload image file to Slack
            # APIでチャンネルIDが必要なため、名前からIDを取得
            ret, channel_id = self.get_channelid(current_channel)
            if ret:
                self.logger.error("チャンネル名が見つかりません:" + current_channel)
                # チャンネルID取得失敗時はEXEにフォールバック
                self.logger.info("Attempting imagepost using external executable (Channel ID not found)...")
                try:
                    timestamp = self.imagepost_exe(image_path, channel=current_channel, token=current_token)
                    return timestamp
                except Exception as e:
                    self.logger.exception("Error posting image for exe (Channel ID not found fallback failed)")
                    return ""

            response = client_to_use.files_upload_v2(
                channel=channel_id, file=image_path, initial_comment=caption
            )
            timestamp = ""
            if response["files"]:
                timestamp = str(response["files"][0]["timestamp"])
            else:
                self.logger.error("Image upload response did not contain file information.")
                return ""

            self.logger.info(f"Image posted successfully. Timestamp: {timestamp}")
            return timestamp

        except Exception as e:
            # API呼び出し失敗時は外部実行ファイルにフォールバック
            self.logger.exception("Error posting image - Attempting fallback to executable...")
            try:
                timestamp = self.imagepost_exe(image_path, channel=current_channel, token=current_token)
                return timestamp
            except Exception as e:
                self.logger.exception("Error posting image for exe (Fallback failed)")
                return ""


    # デコレータ使用するとうまく動かない -> デコレータは削除または調整が必要です
    # @log_decorator
    def imagepost_from_url(self, image_url, caption="", channel=None, token=None):
        """
        Slack APIを使用してURLから画像を投稿します。
        API失敗時は外部実行ファイルにフォールバックします。
        """
        current_channel = channel if channel is not None else self.channel
        current_token = token if token is not None else self.token
        self.logger.info(f"imagepost_from_url start to channel: {current_channel} from url: {image_url}")


        if image_url == "":
            self.logger.error("image_urlが空です。")
            return ""

        use_temp_client = (current_token != self.token) or (channel is not None and channel != self.channel)
        client_to_use = WebClient(token=current_token, ssl=self.ssl_context) if use_temp_client else self.client

        if not client_to_use:
            self.logger.error("Slack client is not initialized or token is invalid.")
            # クライアント初期化失敗時はEXEにフォールバック
            self.logger.info("Attempting imagepost_from_url using external executable...")
            try:
                timestamp = self.imagepost_from_url_exe(image_url, channel=current_channel, token=current_token)
                return timestamp
            except Exception as e:
                self.logger.exception("Error posting image from url for exe (Slack client is not initialized)")
                return ""

        try:
            # Download the image from the URL
            response = requests.get(image_url)
            response.raise_for_status() # HTTPエラーがあれば例外発生
            thumbnail_binary = response.content

            # Upload image file to Slack
            # APIでチャンネルIDが必要なため、名前からIDを取得
            ret, channel_id = self.get_channelid(current_channel)
            if ret:
                self.logger.error("チャンネル名が見つかりません:" + current_channel)
                # チャンネルID取得失敗時はEXEにフォールバック
                self.logger.info("Attempting imagepost_from_url using external executable (Channel ID not found)...")
                try:
                    timestamp = self.imagepost_from_url_exe(image_url, channel=current_channel, token=current_token)
                    return timestamp
                except Exception as e:
                    self.logger.exception("Error posting image from url for exe (Channel ID not found fallback failed)")
                    return ""


            response = client_to_use.files_upload_v2(
                channel=channel_id,
                file=BytesIO(thumbnail_binary),
                initial_comment=caption,
            )
            timestamp = ""
            if response["files"]:
                timestamp = str(response["files"][0]["timestamp"])
            else:
                self.logger.error("Image upload from url response did not contain file information.")
                return ""

            self.logger.info(f"Image posted successfully. Timestamp: {timestamp}")
            return timestamp

        except Exception as e:
            # API呼び出し失敗時は外部実行ファイルにフォールバック
            self.logger.exception("Error posting image from url - Attempting fallback to executable...")
            try:
                timestamp = self.imagepost_from_url_exe(image_url, channel=current_channel, token=current_token)
                return timestamp
            except Exception as e:
                self.logger.exception("Error posting image from url for exe (Fallback failed)")
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
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("Script started.")

    # デフォルトの設定ファイルパスでインスタンスを作成
    logger.info("Creating SlackPoster instance with default config paths...")
    poster_default = SlackPoster()
    logger.info(f"Default Token: {poster_default.token}, Default Channel: {poster_default.channel}")

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


    logger.info(f"Creating SlackPoster instance with alternate config paths: {alternate_api_config}, {alternate_exe_config}...")
    try:
        poster_alternate = SlackPoster(
            slack_api_config_path=alternate_api_config,
            slack_exe_config_path=alternate_exe_config
        )
        logger.info(f"Alternate Token: {poster_alternate.token}, Alternate Channel: {poster_alternate.channel}")

        # 別の設定でテキスト投稿の例
        # timestamp = poster_alternate.textpost("これは別の設定からの投稿です。")
        # if timestamp:
        #     logger.info(f"Posted text with alternate settings, timestamp: {timestamp}")
        # else:
        #     logger.error("Failed to post text with alternate settings.")

    except Exception as e:
        logger.exception("Failed to create SlackPoster instance with alternate configs.")

    logger.info("Script finished.")