from com import log_decorator, CustomLogger
import logging
import ssl
import certifi

if __name__ == "__main__":
    Cl_logger=CustomLogger(flag_datelog = False,dir_path = "./Log",log_encode = "utf-8",maxBytes = 10 * 1024 * 1024,backupCount = 10,showlevel = "INFO",flag_unnecessary_loggers_to_error=True)
    Cl_logger.log_main()
logger = logging.getLogger(__name__)
ssl_context = ssl.create_default_context(cafile=certifi.where())

from configmanager import ConfigManager

import inspect
from traceback import TracebackException as TE
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
from io import BytesIO
import subprocess

default_config_dic = {
    "slack_token": "testtoken",
    "slack_channel": "testchannnel",
}

Cl_Con = ConfigManager(
    default_dic=default_config_dic,
    config_path="./config/slackapi.ini",
    encoding="cp932",
)

default_config_dic = {
    "slack_textpost_exe_path": ".\\dist\\slack_textpost.exe",
    "slack_imagepost_exe_path": ".\\dist\\slack_imagepost.exe",
    "slack_imagepost_from_url_exe_path": ".\\dist\\slack_imagepost_from_url.exe",
}

Cl_Slackexe = ConfigManager(
    default_dic=default_config_dic,
    config_path="./config/slackexe.ini",
    encoding="cp932",
)

TOKEN = Cl_Con.get("slack_token")
CHANNEL = Cl_Con.get("slack_channel")

client = WebClient(token=TOKEN, ssl=ssl_context)  # os.environ.get("SLACK_BOT_TOKEN"))

# ID of the channel you want to send the message to
channel_id = CHANNEL


def get_channelid(name):
    try:
        channels = client.conversations_list()
        if channels["ok"]:
            for i in channels["channels"]:
                if i["name"] == name:
                    return 0, i["id"]
        return 1, ""
    except:
        logger.exception(f"{inspect.currentframe().f_code.co_name}で例外発生")
        return 1, ""


def textpost_exe(text, channel="", token=""):
    cmd_list = [Cl_Slackexe.get("slack_textpost_exe_path")]
    if text:
        cmd_list.append(text)
    else:
        return ""
    if channel:
        cmd_list.append(channel)
        if token:
            cmd_list.append(token)
    result = subprocess.run(cmd_list, encoding="cp932", capture_output=True)
    if result.stdout is not None:
        for i in result.stdout.splitlines():
            logger.debug(i)
    timestamp = ""
    if result.stderr is not None:
        for i in result.stderr.splitlines():
            if i.find("timestamp:") == 0:
                timestamp = i[len("timestamp:") :]
            else:
                logger.error(i)
    return timestamp


@log_decorator(logger)
def imagepost_exe(image_path, channel="", token=""):
    cmd_list = [Cl_Slackexe.get("slack_imagepost_exe_path")]
    if image_path:
        cmd_list.append(image_path)
    else:
        return ""
    if channel:
        cmd_list.append(channel)
        if token:
            cmd_list.append(token)
    result = subprocess.run(cmd_list, encoding="cp932", capture_output=True)
    if result.stdout is not None:
        for i in result.stdout.splitlines():
            logger.debug(i)
    timestamp = ""
    if result.stderr is not None:
        for i in result.stderr.splitlines():
            if i.find("timestamp:") == 0:
                timestamp = i[len("timestamp:") :]
            else:
                if "UserWarning" not in i:
                    logger.error(i)
    return timestamp


@log_decorator(logger)
def imagepost_from_url_exe(image_url, channel="", token=""):
    cmd_list = [Cl_Slackexe.get("slack_imagepost_from_url_exe_path")]
    if image_url:
        cmd_list.append(image_url)
    else:
        return ""
    if channel:
        cmd_list.append(channel)
        if token:
            cmd_list.append(token)
    result = subprocess.run(cmd_list, encoding="cp932", capture_output=True)
    if result.stdout is not None:
        for i in result.stdout.splitlines():
            logger.debug(i)
    timestamp = ""
    if result.stderr is not None:
        for i in result.stderr.splitlines():
            if i.find("timestamp:") == 0:
                timestamp = i[len("timestamp:") :]
            else:
                if "UserWarning" not in i:
                    logger.error(i)
    return timestamp


# デコレータ使用するとうまく動かない
# @log_decorator
def textpost(text, channel=CHANNEL, token=TOKEN):
    logger.info("testpost start")
    try:
        if text == "":
            logger.error("メッセージが空です。")
            return ""
        if channel == "":
            channel = CHANNEL
        if token == "":
            token = TOKEN
        client = WebClient(token=token, ssl=ssl_context)
        # Call the chat.postMessage method using the WebClient
        result = client.chat_postMessage(
            channel=channel,
            text=text,
        )
        timestamp = result["ts"]
        logger.info(f"message posted successfully. Timestamp: {timestamp}")
        return timestamp

    except Exception as e:
        logger.exception(f"{inspect.currentframe().f_code.co_name}で例外発生")
        try:
            timestamp = textpost_exe(text, channel=channel, token=token)
            return timestamp
        except Exception as e:
            logger.exception("textpost_exeで例外発生")
            return ""


# デコレータ使用するとうまく動かない
# @log_decorator
def imagepost(image_path, caption="", channel=CHANNEL, token=TOKEN):
    logger.info("imagepost start")
    try:
        if image_path == "":
            logger.error("image_pathが空です。")
            return ""
        if channel == "":
            channel = CHANNEL
        if token == "":
            token = TOKEN
        client = WebClient(token=token, ssl=ssl_context)
        # Upload image file to Slack
        ret, channel_id = get_channelid(channel)
        if ret:
            logger.error("チャンネル名が見つかりません:" + channel)
            return ""
        response = client.files_upload_v2(
            channel=channel_id, file=image_path, initial_comment=caption
        )
        for i in response["files"]:
            timestamp = str(i["timestamp"])
            break
        logger.info(f"Image posted successfully. Timestamp: {timestamp}")
        return timestamp

    except Exception as e:
        logger.exception("Error posting image")
        try:
            timestamp = imagepost_exe(image_path, channel=channel, token=token)
            return timestamp
        except Exception as e:
            logger.exception("Error posting image for exe")
            return ""


# デコレータ使用するとうまく動かない
# @log_decorator
def imagepost_from_url(image_url, caption="", channel=CHANNEL, token=TOKEN):
    logger.info("imagepost_from_url start")
    try:
        if image_url == "":
            logger.error("image_pathが空です。")
            return ""
        if channel == "":
            channel = CHANNEL
        if token == "":
            token = TOKEN
        # Download the image from the URL
        response = requests.get(image_url)
        thumbnail_binary = response.content

        client = WebClient(token=token, ssl=ssl_context)
        # Upload image file to Slack
        ret, channel_id = get_channelid(channel)
        if ret:
            logger.error("チャンネル名が見つかりません:" + channel)
            return ""
        response = client.files_upload_v2(
            channel=channel_id,
            file=BytesIO(thumbnail_binary),
            initial_comment=caption,
        )
        for i in response["files"]:
            timestamp = str(i["timestamp"])
            break
        logger.info(f"Image posted successfully. Timestamp: {timestamp}")
        return timestamp

    except Exception as e:
        logger.exception("Error posting image from url")
        try:
            timestamp = imagepost_from_url_exe(image_url, channel=channel, token=token)
            return timestamp
        except Exception as e:
            logger.exception("Error posting image from url for exe")
            return ""
