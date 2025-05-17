from com import log_decorator, CustomLogger
import logging
import ssl
import certifi

if __name__ == "__main__":
    Cl_logger=CustomLogger(flag_datelog = False,dir_path = "./Log",log_encode = "utf-8",maxBytes = 10 * 1024 * 1024,backupCount = 10,showlevel = "INFO")
    Cl_logger.log_main()
logger = logging.getLogger(__name__)
ssl_context = ssl.create_default_context(cafile=certifi.where())

import os
import configparser
from pathlib import Path

class ConfigManager:
    """設定ファイルを管理するクラス"""

    @log_decorator(logger)
    def __init__(
        self,
        default_dic: dict,
        type_dic: dict = {},
        config_path: str = os.path.basename(os.getcwd()) + ".ini",
        encoding: str = "utf-8",
    ):
        self.default_dic_initial = default_dic.copy()
        self.config_dic = {}  # 型変換後の値を格納
        self.type_dic = type_dic
        self.config_path = str(Path(config_path).absolute())
        self.encoding = encoding

        # config_dic のキーの順序を default_dic_initial に合わせる
        for key in self.default_dic_initial.keys():
            self.config_dic[key] = None # プレースホルダー

        if not os.path.exists(self.config_path):
            logger.info(f"設定ファイルが見つかりません。テンプレートを作成します: {self.config_path}")
            self._apply_type_to_initial_defaults()
            self.config_generator()
        else:
            logger.info(f"設定ファイルを読み込みます: {self.config_path}")
            self._load_config()

    def _apply_type_to_initial_defaults(self):
        """
        初期デフォルト値 (self.default_dic_initial) に型定義を適用し、
        結果を self.config_dic に格納する。
        主にファイルが最初に生成される際や、読み込み失敗時のフォールバックに使用。
        """
        for key, default_raw_value in self.default_dic_initial.items():
            if self.type_dic and key in self.type_dic:
                expected_type = self.type_dic[key]
                # default_raw_value は Python の型を持つ可能性がある
                if isinstance(default_raw_value, expected_type):
                    self.config_dic[key] = default_raw_value
                else:
                    # 文字列に変換してから _convert_value へ (bool(1) -> "1" -> True)
                    # fallbackは元のPythonオブジェクトそのもの
                    converted_value = self._convert_value(str(default_raw_value), expected_type, key, default_raw_value)
                    self.config_dic[key] = converted_value
            else:
                # type_dic に定義がない場合は、そのままの値を使用
                self.config_dic[key] = default_raw_value
            logger.debug(f"初期デフォルト適用: {key}: {self.config_dic.get(key)} (型: {type(self.config_dic.get(key)).__name__})")


    def _load_config(self):
        """設定ファイルを読み込み、型チェックと変換を行い self.config_dic を更新する。"""
        config_ini = configparser.ConfigParser()
        try:
            read_files = config_ini.read(self.config_path, encoding=self.encoding)
            if not read_files:
                logger.warning(f"設定ファイル {self.config_path} が読み込めませんでした。初期デフォルト値を使用します。")
                self._apply_type_to_initial_defaults() # 初期デフォルトを適用
                return
        except configparser.Error as e:
            logger.error(f"設定ファイル {self.config_path} の解析エラー: {e}。初期デフォルト値を使用します。")
            self._apply_type_to_initial_defaults() # 初期デフォルトを適用
            return

        read_section = config_ini["DEFAULT"] if "DEFAULT" in config_ini else {}

        for key in self.default_dic_initial.keys():
            value_from_file_str = read_section.get(key) # INIファイルからは文字列として取得
            initial_default_typed_value = self.default_dic_initial[key] # 元のdefault_dicの値

            # フォールバック先の値として、まずは初期デフォルト値を型変換したものを用意
            fallback_value_for_key = initial_default_typed_value
            if self.type_dic and key in self.type_dic:
                expected_type = self.type_dic[key]
                if not isinstance(initial_default_typed_value, expected_type):
                     # 初期デフォルトも念のため型変換（既に _apply_type_to_initial_defaults で行われているはずだが、安全のため）
                    fallback_value_for_key = self._convert_value(str(initial_default_typed_value), expected_type, key, initial_default_typed_value)


            if value_from_file_str is not None: # 設定ファイルにキーが存在する場合
                if self.type_dic and key in self.type_dic:
                    expected_type = self.type_dic[key]
                    self.config_dic[key] = self._convert_value(value_from_file_str, expected_type, key, fallback_value_for_key)
                else:
                    # 型定義がない場合はファイルからの文字列をそのまま使用
                    self.config_dic[key] = value_from_file_str
            else: # 設定ファイルにキーが存在しない場合
                logger.info(f"キー '{key}' が設定ファイルにありません。初期デフォルト値 (型適用後) '{fallback_value_for_key}' を使用します。")
                self.config_dic[key] = fallback_value_for_key
            
            logger.info(f"読み込み後: {key}: {self.config_dic.get(key)} (型: {type(self.config_dic.get(key)).__name__})")
        
        # default_dic_initial にはなく、ファイルにのみ存在する設定の扱い (オプション)
        for key_in_file in read_section.keys():
            if key_in_file not in self.default_dic_initial:
                value_str = read_section[key_in_file]
                # type_dic に定義があれば型変換を試みる、なければ文字列として追加
                if self.type_dic and key_in_file in self.type_dic:
                    expected_type = self.type_dic[key_in_file]
                    # 未知のキーに対するフォールバックは難しいので、変換失敗時はNoneにするかエラー
                    converted = self._convert_value(value_str, expected_type, key_in_file, None) # フォールバックはNone
                    if converted is not None: # 変換成功時のみ（Noneが有効な値でない場合）
                        self.config_dic[key_in_file] = converted
                        logger.info(f"ファイルから追加読込 (型変換有): {key_in_file}: {converted} (型: {type(converted).__name__})")
                    else:
                        logger.warning(f"ファイルにのみ存在するキー '{key_in_file}' の値 '{value_str}' を型 '{expected_type.__name__}' に変換できませんでした。スキップします。")
                else:
                    self.config_dic[key_in_file] = value_str # 型定義なしなら文字列
                    logger.info(f"ファイルから追加読込 (型定義なし): {key_in_file}: {value_str} (型: {type(value_str).__name__})")


    def _convert_value(self, value_str: str, expected_type, key: str, fallback_value):
        """文字列を指定された型に変換する。失敗した場合は警告を出し、フォールバック値を返す。"""
        try:
            if expected_type == bool:
                val_lower = value_str.lower()
                if val_lower in ('true', '1', 'yes', 'on'):
                    return True
                elif val_lower in ('false', '0', 'no', 'off'):
                    return False
                else:
                    raise ValueError(f"ブール値として解釈できません: '{value_str}'")
            elif expected_type == int:
                return int(value_str)
            elif expected_type == float:
                return float(value_str)
            elif expected_type == str:
                return value_str
            # 他の型 (例: list, dict from string) が必要であればここに追加
            # elif expected_type == list:
            #     if isinstance(value_str, str) and value_str.startswith('[') and value_str.endswith(']'):
            #         import ast
            #         return ast.literal_eval(value_str) # 安全なリテラル評価
            #     raise ValueError("リストとして解釈できません。例: '[item1, item2]'")
            else:
                # サポートされていない型定義の場合
                logger.warning(
                    f"キー '{key}' の値 '{value_str}' に対する型 '{expected_type.__name__}' の自動変換は未サポートです。"
                    f"フォールバック値 '{fallback_value}' (型: {type(fallback_value).__name__}) を使用します。"
                )
                return fallback_value
        except ValueError as ve: # int(), float(), bool() および手動raise ValueError
            logger.warning(
                f"設定値 '{key}'='{value_str}' の型変換失敗 ({ve})。期待型: {expected_type.__name__}。 "
                f"フォールバック値 '{fallback_value}' (型: {type(fallback_value).__name__}) を使用します。"
            )
            return fallback_value
        except Exception as e: # その他の予期せぬエラー
            logger.error(
                f"設定値 '{key}'='{value_str}' の型変換中に予期せぬエラー ({type(e).__name__}: {e})。 "
                f"フォールバック値 '{fallback_value}' (型: {type(fallback_value).__name__}) を使用します。"
            )
            return fallback_value

    @log_decorator(logger)
    def reload(self):
        logger.debug(f"設定ファイルをリロードします: {self.config_path}")
        old_config_dic_snapshot = self.config_dic.copy()

        if not os.path.exists(self.config_path):
            logger.warning(f"リロード試行時、設定ファイル {self.config_path} が見つかりません。")
            # ファイルがない場合、元のコードではテンプレート作成を行っていた。
            # 初期デフォルト値で再初期化し、ファイルも生成する。
            self._apply_type_to_initial_defaults()
            self.config_generator()
        else:
            self._load_config() # ファイル読み込みと型変換

        # 変更点のログ出力
        all_keys = set(old_config_dic_snapshot.keys()) | set(self.config_dic.keys())
        for key in sorted(list(all_keys)):
            old_value = old_config_dic_snapshot.get(key)
            new_value = self.config_dic.get(key)
            # repr() を使うと型情報がより明確になることがある（特に文字列と数値）
            if old_value != new_value or type(old_value) != type(new_value):
                logger.info(
                    f"設定変更 key=[{key}]: {repr(old_value)} (型: {type(old_value).__name__}) "
                    f"→ {repr(new_value)} (型: {type(new_value).__name__})"
                )

    @log_decorator(logger)
    def config_generator(self):
        """現在の self.config_dic の内容を設定ファイルに書き出す。"""
        try:
            dir_name = os.path.dirname(self.config_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                logger.info(f"保存先ディレクトリを作成しました: {dir_name}")
            
            config = configparser.ConfigParser()
            config.optionxform = str # キーの大文字・小文字を保持
            
            # configparser は値を文字列として書き込むため、Python オブジェクトを文字列に変換
            # self.config_dic には既に型変換済みの値が入っている
            default_section_to_write = {k: str(v) for k, v in self.config_dic.items() if v is not None} # Noneは書き込まないオプション
            config["DEFAULT"] = default_section_to_write
            
            with open(self.config_path, "w", encoding=self.encoding) as configfile:
                config.write(configfile)
            logger.info(f"設定ファイルを生成/更新しました: {self.config_path}")
        except IOError as e:
            logger.error(f"設定ファイルの書き込みに失敗しました: {self.config_path}, IOエラー: {e}")
            raise
        except Exception as e:
            logger.error(f"設定ファイルの作成中に予期せぬエラーが発生しました: {self.config_path}, エラー: {e}")
            raise

    def get(self, key: str, default_override=None):
        """
        設定値を取得する。
        キーが存在しない場合、default_override が指定されていればそれを返す。
        指定されていなければ None を返す (self.config_dic.get の挙動)。
        """
        if default_override is not None:
            return self.config_dic.get(key, default_override)
        return self.config_dic.get(key)

    def allget(self) -> dict:
        """現在の全ての設定値 (型変換後) のコピーを返す。"""
        return self.config_dic.copy()

    @log_decorator(logger)
    def set(self, key: str, value_to_set):
        """
        設定値をメモリ上に設定する。type_dic に基づいて型チェックと変換を試みる。
        成功すれば値を更新。失敗した場合は警告を出し、値は変更されない。
        """
        original_value = self.config_dic.get(key) # 変更前の値（フォールバックや比較用）

        if self.type_dic and key in self.type_dic:
            expected_type = self.type_dic[key]
            
            if isinstance(value_to_set, expected_type): # 既に期待する型の場合
                converted_value = value_to_set
            else: # 型が異なる場合、文字列として変換を試みる
                # フォールバックには、現在のメモリ上の値を使用する
                # これにより、不正なset操作で値が意図せず初期デフォルトに戻るのを防ぐ
                fallback_for_set = original_value if original_value is not None else self.default_dic_initial.get(key)
                converted_value = self._convert_value(str(value_to_set), expected_type, key, fallback_for_set)

            # 変換結果が期待する型であるか、かつ変換が実質的に成功したかを確認
            if isinstance(converted_value, expected_type):
                if self.config_dic.get(key) != converted_value : # 値が実際に変更される場合のみログ出力と更新
                    self.config_dic[key] = converted_value
                    logger.info(f"設定値セット (型変換/検証済): key='{key}', value={repr(converted_value)} (入力: {repr(value_to_set)})")
                else:
                    logger.debug(f"設定値セット試行 (変更なし): key='{key}', value={repr(converted_value)}")
            else:
                logger.warning(
                    f"キー '{key}' に値 {repr(value_to_set)} (入力型: {type(value_to_set).__name__}) をセット試行しましたが、"
                    f"期待型 '{expected_type.__name__}' への変換結果が不正です (結果: {repr(converted_value)}, 型: {type(converted_value).__name__})。"
                    "値は変更されません。"
                )
        else: # type_dic にキーがない (型定義がない) 場合
            if self.config_dic.get(key) != value_to_set:
                self.config_dic[key] = value_to_set
                logger.info(f"設定値セット (型定義なし): key='{key}', value={repr(value_to_set)}")
            else:
                 logger.debug(f"設定値セット試行 (型定義なし, 変更なし): key='{key}', value={repr(value_to_set)}")
        
        # default_dic_initial にない新しいキーがセットされた場合にも対応
        if key not in self.default_dic_initial and key in self.config_dic:
            logger.info(f"キー '{key}' は初期デフォルト辞書にない新しいキーとして設定/更新されました。")

    @log_decorator(logger)
    def save(self):
        """現在の設定をファイルに保存する。"""
        logger.info(f"設定をファイルに保存します: {self.config_path}")
        self.config_generator()

# === 以下、テスト用のコード (ConfigManagerクラス定義の外) ===
if __name__ == '__main__':
    # --- テスト用のロガー設定 ---
    # ConfigManager内で使われるロガーインスタンスと同じ設定をテストコード側でも行う
    logging.basicConfig(
        level=logging.INFO, # INFO以上をコンソールに出力
        format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # `logger = logging.getLogger(__name__)` は既にクラス定義の上にあるので、それが使われる。
    # もしConfigManagerが別の名前でロガーを取得しているなら、それに合わせる。
    # この例では、ConfigManager内の `logger` は `logging.getLogger(__name__)` であり、
    # `__name__` はこのファイルが直接実行された場合は `'__main__'` になる。

    main_logger = logging.getLogger(__name__) # テストコード自体が使うロガー
    main_logger.info("======== ConfigManager テスト開始 ========")

    # --- テストデータ ---
    default_config = {
        "app_name": "MyApplication",
        "version": "1.0",
        "debug_mode": "true", # bool期待
        "port_number": "8080", # int期待
        "timeout_seconds": "30.5", # float期待
        "feature_flags": "flagA,flagB", # str (list変換は今回未実装)
        "empty_value_test": "", # str
        "value_missing_in_file": "default for missing", # ファイルに意図的に含めない
        "value_with_bad_type_in_file": "original_good_bool", # ファイル内で不正な型にするテスト用 (bool期待)
        "untyped_setting": 12345, # 型定義なし (Pythonのint)
    }
    type_config = {
        "app_name": str,
        "version": str,
        "debug_mode": bool,
        "port_number": int,
        "timeout_seconds": float,
        "feature_flags": str, # 将来的には list なども考慮可能
        "empty_value_test": str,
        "value_missing_in_file": str,
        "value_with_bad_type_in_file": bool,
        # "untyped_setting" は type_config に含めない
    }
    test_ini_file = "test_app_config.ini"

    # --- 1. 初期化 (設定ファイルが存在しない場合) ---
    main_logger.info("\n--- Test 1: 初期化 (ファイルなし) ---")
    if os.path.exists(test_ini_file):
        os.remove(test_ini_file)
    
    cfg_manager = ConfigManager(default_config, type_config, config_path=test_ini_file)
    
    main_logger.info("生成されたファイルの内容:")
    if os.path.exists(test_ini_file):
        with open(test_ini_file, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        main_logger.error(f"{test_ini_file} が生成されませんでした。")

    main_logger.info("初期化後の値:")
    assert cfg_manager.get("debug_mode") is True
    assert cfg_manager.get("port_number") == 8080
    assert cfg_manager.get("timeout_seconds") == 30.5
    assert cfg_manager.get("untyped_setting") == 12345 # 型定義なしなので元の型
    main_logger.info(f"debug_mode: {cfg_manager.get('debug_mode')} (type: {type(cfg_manager.get('debug_mode')).__name__})")
    main_logger.info(f"untyped_setting: {cfg_manager.get('untyped_setting')} (type: {type(cfg_manager.get('untyped_setting')).__name__})")


    # --- 2. 設定ファイルを手動で変更し、リロード ---
    main_logger.info("\n--- Test 2: ファイル変更とリロード ---")
    with open(test_ini_file, 'w', encoding='utf-8') as f:
        f.write("[DEFAULT]\n")
        f.write("app_name = TestApp Reloaded\n")
        f.write("debug_mode = false\n") # 正しい形式
        f.write("port_number = not_an_int\n") # 不正な形式
        f.write("timeout_seconds = 60\n") # intだがfloatに変換可能
        # "value_missing_in_file" はここでも含めない
        f.write("value_with_bad_type_in_file = NotBool\n") # 不正なブール値
        f.write("new_key_from_file = hello_from_file\n") # default_dicにないキー
    
    main_logger.info("リロード前のport_number: " + str(cfg_manager.get("port_number")))
    cfg_manager.reload()
    
    main_logger.info("リロード後の値:")
    assert cfg_manager.get("app_name") == "TestApp Reloaded"
    assert cfg_manager.get("debug_mode") is False
    assert cfg_manager.get("port_number") == 8080 # 不正だったので初期デフォルトにフォールバック
    assert cfg_manager.get("timeout_seconds") == 60.0 # "60" -> 60.0
    assert cfg_manager.get("value_missing_in_file") == "default for missing" # ファイルになかったので初期デフォルト
    assert cfg_manager.get("value_with_bad_type_in_file") is True # 不正だったので初期デフォルト(true)にフォールバック
    assert cfg_manager.get("new_key_from_file") == "hello_from_file" # default_dicになくても読み込まれる(型定義なし)
    main_logger.info(f"port_number: {cfg_manager.get('port_number')} (type: {type(cfg_manager.get('port_number')).__name__})")
    main_logger.info(f"timeout_seconds: {cfg_manager.get('timeout_seconds')} (type: {type(cfg_manager.get('timeout_seconds')).__name__})")
    main_logger.info(f"new_key_from_file: {cfg_manager.get('new_key_from_file')} (type: {type(cfg_manager.get('new_key_from_file')).__name__})")

    # --- 3. set メソッドのテスト ---
    main_logger.info("\n--- Test 3: set メソッド ---")
    cfg_manager.set("debug_mode", "1") # 文字列 '1' -> True
    assert cfg_manager.get("debug_mode") is True
    cfg_manager.set("port_number", 9090) # int -> int
    assert cfg_manager.get("port_number") == 9090
    cfg_manager.set("port_number", "bad_value") # 文字列 (intに変換不可) -> 値は変わらないはず
    assert cfg_manager.get("port_number") == 9090 # 変更されない
    cfg_manager.set("app_name", 12345) # intだがstr型期待 -> "12345" に変換される
    assert cfg_manager.get("app_name") == "12345" 
    cfg_manager.set("new_runtime_setting", "runtime_val") # 型定義なしで新規追加
    assert cfg_manager.get("new_runtime_setting") == "runtime_val"
    cfg_manager.set("new_typed_runtime_setting", "true",) # このキーはtype_configにないが、もし動的に型定義を追加できれば…
                                                      # 現状は型定義なしとして扱われる
    type_config["new_typed_runtime_setting"] = bool # 型定義を後から追加（managerは再生成しないと反映されないがテストのため）
    cfg_manager.type_dic["new_typed_runtime_setting"] = bool # 強制的にマネージャのtype_dicを更新
    cfg_manager.set("new_typed_runtime_setting", "false")
    assert cfg_manager.get("new_typed_runtime_setting") is False


    # --- 4. save メソッドのテスト ---
    main_logger.info("\n--- Test 4: save メソッド ---")
    cfg_manager.save()
    main_logger.info("保存後のファイル内容:")
    if os.path.exists(test_ini_file):
        with open(test_ini_file, 'r', encoding='utf-8') as f:
            print(f.read())
    
    # --- 5. allget メソッドのテスト ---
    main_logger.info("\n--- Test 5: allget メソッド ---")
    all_conf = cfg_manager.allget()
    main_logger.info(f"allget() result: {all_conf}")
    all_conf["port_number"] = 0 # コピーなので元のConfigManagerインスタンスには影響しない
    assert cfg_manager.get("port_number") != 0

    # --- 6. ファイル削除後のリロードテスト ---
    main_logger.info("\n--- Test 6: ファイル削除とリロード ---")
    if os.path.exists(test_ini_file):
        os.remove(test_ini_file)
    cfg_manager.reload() # ファイルがないので、初期デフォルト値で再生成される
    assert cfg_manager.get("port_number") == 8080 # 初期デフォルトの '8080' -> 8080
    assert cfg_manager.get("debug_mode") is True   # 初期デフォルトの 'true' -> True
    main_logger.info(f"ファイル削除・リロード後のport_number: {cfg_manager.get('port_number')}")


    main_logger.info("\n======== ConfigManager テスト終了 ========")
    # テスト後クリーンアップ
    if os.path.exists(test_ini_file):
        os.remove(test_ini_file)