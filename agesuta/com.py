import os
import logging
from datetime import datetime
from logging import Formatter
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL, NOTSET
from rich.logging import RichHandler
from logging.handlers import RotatingFileHandler
from chardet.universaldetector import UniversalDetector
import inspect
import re
import sys

import ssl
import certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())

# ANSI エスケープシーケンスを除去する Formatter
class NoColorFormatter(logging.Formatter):
    # ANSI エスケープシーケンスにマッチする正規表現
    ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    def format(self, record):
        msg = super().format(record)
        # ANSI シーケンスを空文字に置換
        return self.ANSI_ESCAPE.sub("", msg)


class CustomLevelRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        """
        ファイル名を basename.<番号>.<timestamp>.log にしてローテート。
        ローテートのたびに既存ファイルの番号を+1し、最新を .1.<timestamp>.log にする。
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        base, ext = os.path.splitext(self.baseFilename)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        log_dir = os.path.dirname(self.baseFilename)
        base_name = os.path.basename(base)

        pattern = re.compile(
            rf"^{re.escape(base_name)}\.(\d+)\.\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}{re.escape(ext)}$"
        )
        files_with_index = []

        for fname in os.listdir(log_dir):
            match = pattern.match(fname)
            if match:
                idx = int(match.group(1))
                files_with_index.append((idx, fname))

        # 番号が大きい順にずらす
        for idx, fname in sorted(files_with_index, reverse=True):
            full_path = os.path.join(log_dir, fname)
            if idx >= self.backupCount:
                os.remove(full_path)
            else:
                new_name = f"{base_name}.{idx + 1}.{fname.split('.', 2)[2]}"
                os.rename(os.path.join(log_dir, fname), os.path.join(log_dir, new_name))

        # 現在のログファイルを .1.<timestamp>.log にローテート
        dfn = os.path.join(log_dir, f"{base_name}.1.{timestamp}{ext}")
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)

        if not self.delay:
            self.stream = self._open()


class CustomDateRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        """
        ファイル名を basename_<timestamp>.<番号>.log にしてローテート。
        ローテートのたびに既存ファイルの番号を+1し、最新を .1.<timestamp>.log にする。
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        base, ext = os.path.splitext(self.baseFilename)
        log_dir = os.path.dirname(self.baseFilename)
        base_name = os.path.basename(base)

        # debug.N.log にマッチするファイルを探す
        pattern = re.compile(rf"^{re.escape(base_name)}\.(\d+){re.escape(ext)}$")
        files_with_index = []

        for fname in os.listdir(log_dir):
            match = pattern.match(fname)
            if match:
                idx = int(match.group(1))
                files_with_index.append((idx, fname))

        # 番号が大きい順にずらす
        for idx, fname in sorted(files_with_index, reverse=True):
            full_path = os.path.join(log_dir, fname)
            if idx >= self.backupCount:
                os.remove(full_path)
            else:
                new_name = f"{base_name}.{idx + 1}{ext}"
                os.rename(os.path.join(log_dir, fname), os.path.join(log_dir, new_name))

        # 現在のログファイルを .1.log にローテート
        dfn = os.path.join(log_dir, f"{base_name}.1{ext}")
        if os.path.exists(dfn):
            os.remove(dfn)
        self.rotate(self.baseFilename, dfn)

        if not self.delay:
            self.stream = self._open()


class CustomLogger:
    def __init__(
        self,
        flag_datelog: bool = False,
        dir_path: str = "./Log",
        log_encode: str = "utf-8",
        maxBytes: int = 10 * 1024 * 1024,
        backupCount: int = 10,
        showlevel="INFO",
        flag_unnecessary_loggers_to_error=True,
    ):
        self.flag_datelog = bool(flag_datelog)
        self.dir_path = str(dir_path)
        self.log_encode = str(log_encode)
        self.maxBytes = int(maxBytes)
        self.backupCount = int(backupCount)
        level_dic = {
            "DEBUG": DEBUG,
            "INFO": INFO,
            "WARNING": WARNING,
            "ERROR": ERROR,
            "CRITICAL": CRITICAL,
            "NOTSET": NOTSET,
        }
        self.showlevel = level_dic.get(showlevel.upper(), INFO)
        if flag_unnecessary_loggers_to_error:
            logger_names = [
                "werkzeug",
                "httpcore.http11",
                "urllib3.connectionpool",
                "googleapiclient.discovery_cache",
                "googleapiclient.discovery",
                "selenium.webdriver.remote.remote_connection",
                "WDM",
                "oauthlib.oauth1.rfc5849",
                "requests_oauthlib.oauth1_auth",
                "httpx"
            ]
            for name in logger_names:
                logging.getLogger(name).setLevel(logging.ERROR)

    def encode_detect(self, filepath):
        if not os.path.exists(filepath):
            return 1, ""
        try:
            try:
                detector = UniversalDetector()
                with open(filepath, "rb") as f:
                    while True:
                        binary = f.readline()
                        if binary == b"":
                            break
                        detector.feed(binary)
                        if detector.done:
                            break
            finally:
                detector.close()
            # print("encoding:" + str(detector.result["encoding"]))
            if detector.result["encoding"] is None:
                return 0, "CP932"
            elif detector.result["encoding"] in ["utf-8", "UTF-8-SIG"]:
                return 0, "utf-8"
            elif detector.result["encoding"] in ["CP932", "SHIFT_JIS", "Windows-1254"]:
                return 0, "CP932"
            else:
                return 0, detector.result["encoding"]
        except:
            return 2, ""

    def change_encode(self, filepath, after_encode):
        try:
            ret, before_encode = self.encode_detect(filepath)
            if ret == 1:
                # ファイルがない場合はそのまま返す
                return 1
            if before_encode == after_encode:
                # 再エンコードが不要な場合はそのまま返す
                return 0
            try:
                os.rename(filepath, filepath + "_bk")
            except:
                if os.path.exists(filepath):
                    os.remove(filepath)
                # リネーム失敗時は削除して返す
                return 1
            if ret == 2:
                # エンコードの読み取り失敗時はリネームして返す
                return 1
            try:
                with open(filepath + "_bk", "r", encoding=before_encode) as f:
                    txt = f.read()
                with open(filepath, "w", encoding=after_encode) as f:
                    f.write(txt)
                os.remove(filepath + "_bk")
            except:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return 1
            return 0
        except:
            return 1

    def get_script_display_name(self):
        # PyInstallerなどでexe化している場合
        if getattr(sys, "frozen", False):
            # sys.executable はexeのパスなので、
            # ここでbasename (拡張子なし) を取得
            base = os.path.basename(sys.executable)
            name, _ = os.path.splitext(base)
            return name + "_"
        else:
            # 通常のスクリプト実行の場合
            # __main__モジュールの__file__が使えるのでそれを利用
            try:
                # __main__モジュールがあれば
                import __main__

                if hasattr(__main__, "__file__"):
                    base = os.path.basename(__main__.__file__)
                    name, _ = os.path.splitext(base)
                    return name + "_"
            except Exception:
                pass

            # もし上記で取得できなかった場合は、inspectでスタックから探す
            for frame in inspect.stack():
                module = inspect.getmodule(frame[0])
                if module and hasattr(module, "__file__"):
                    base = os.path.basename(module.__file__)
                    name, _ = os.path.splitext(base)
                    return name + "_"
            # もし何も見つからなければ空文字
            return ""

    def log_main(self):
        handlers = []
        importname = self.get_script_display_name()

        # ストリームハンドラの設定
        rich_handler: RichHandler = RichHandler(rich_tracebacks=True)
        rich_handler.setLevel(self.showlevel)
        rich_handler.setFormatter(NoColorFormatter("%(message)s"))
        handlers.append(rich_handler)

        # 保存先の有無チェック
        if not os.path.isdir(self.dir_path):
            os.makedirs(self.dir_path, exist_ok=True)

        # ファイルハンドラの設定
        if self.flag_datelog:
            logfile_path = f"{self.dir_path}/{importname}{datetime.now():%Y-%m-%d}.log"
            if os.path.exists(logfile_path):
                ret = self.change_encode(logfile_path, self.log_encode)
            file_handler = CustomDateRotatingFileHandler(
                logfile_path,
                "a",
                maxBytes=self.maxBytes,
                backupCount=self.backupCount,
                encoding=self.log_encode,
            )
            file_handler.setLevel(DEBUG)
            file_handler.setFormatter(
                # Formatter("%(asctime)s [%(levelname).4s] %(filename)s %(funcName)s %(lineno)d: %(message)s")
                NoColorFormatter(
                    "%(asctime)s [%(levelname)s] %(name)s %(filename)s %(funcName)s %(lineno)d: %(message)s"
                )
            )
            handlers.append(file_handler)

            # ルートロガーの設定
            logging.basicConfig(level=NOTSET, handlers=handlers)
        else:
            loggger_dic = {
                f"{importname}0_debug": DEBUG,
                f"{importname}1_info": INFO,
                f"{importname}2_warning": WARNING,
                f"{importname}3_error": ERROR,
            }
            for i in list(loggger_dic.keys()):
                logfile_path = f"{self.dir_path}/{i}.log"
                if os.path.exists(logfile_path):
                    ret = self.change_encode(logfile_path, self.log_encode)
                logger_temp = CustomLevelRotatingFileHandler(
                    logfile_path,
                    "a",
                    maxBytes=self.maxBytes,
                    backupCount=self.backupCount,
                    encoding=self.log_encode,
                )
                logger_temp.setLevel(loggger_dic[i])
                logger_temp.setFormatter(
                    # Formatter("%(asctime)s [%(levelname).4s] %(filename)s %(funcName)s %(lineno)d: %(message)s")
                    NoColorFormatter(
                        "%(asctime)s [%(levelname)s] %(name)s %(filename)s %(funcName)s %(lineno)d: %(message)s"
                    )
                )
                handlers.append(logger_temp)

            # ルートロガーの設定
            logging.basicConfig(level=NOTSET, handlers=handlers)


def log_decorator(logger):
    def _log_decorator(func):
        def wrapper(*args, **kwargs):
            local_args = locals()
            try:
                logger.debug(f"start: {func.__name__}  args: {str(local_args)}")
                return_val = func(*args, **kwargs)
                logger.debug(f"  end: {func.__name__}  ret: {str(return_val)}")
                # logger.debug(f"  end: {func.__name__}")
                return return_val
            except Exception as e:
                logger.error(f"error: {func.__name__}")
                raise e

        return wrapper

    return _log_decorator


if __name__ == "__main__":
    Cl_logger = CustomLogger(flag_datelog=False, dir_path="./Log", log_encode="utf-8")
    Cl_logger.log_main()
    logger = logging.getLogger(__name__)
    logger.debug("テスト: debug")
    logger.info("テスト: info")
    logger.warning("テスト: warning")
    logger.error("テスト: error")
    logger.critical("テスト: critical")
    os.system("PAUSE")
