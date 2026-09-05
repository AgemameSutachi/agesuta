import os
import pytest

from agesuta.configmanager import ConfigManager


def make_manager(tmp_path, default_dic, type_dic=None, filename="cfg.ini"):
    cfg_path = str(tmp_path / filename)
    return ConfigManager(default_dic, type_dic, config_path=cfg_path)


def test_init_creates_file_with_type_conversion(tmp_path):
    default_dic = {"debug": "true", "count": "5", "name": "app"}
    type_dic = {"debug": bool, "count": int}
    cm = make_manager(tmp_path, default_dic, type_dic)

    assert os.path.exists(cm.config_path)
    assert cm.get("debug") is True
    assert cm.get("count") == 5
    assert cm.get("name") == "app"


def test_get_default_override(tmp_path):
    cm = make_manager(tmp_path, {"name": "app"})
    assert cm.get("missing") is None
    assert cm.get("missing", "fallback") == "fallback"


def test_set_with_valid_and_invalid_conversion(tmp_path):
    default_dic = {"count": "5"}
    type_dic = {"count": int}
    cm = make_manager(tmp_path, default_dic, type_dic)

    cm.set("count", "10")
    assert cm.get("count") == 10

    cm.set("count", "not_an_int")
    assert cm.get("count") == 10  # 変換失敗時は変更されない

    cm.set("count", 20)
    assert cm.get("count") == 20


def test_convert_value_bool_int_float_str(tmp_path):
    cm = make_manager(tmp_path, {"name": "app"})

    assert cm._convert_value("true", bool, "x", False) is True
    assert cm._convert_value("no", bool, "x", False) is False
    assert cm._convert_value("invalid_bool", bool, "x", "FALLBACK") == "FALLBACK"

    assert cm._convert_value("123", int, "x", 0) == 123
    assert cm._convert_value("abc", int, "x", 99) == 99

    assert cm._convert_value("1.5", float, "x", 0.0) == 1.5

    assert cm._convert_value("hello", str, "x", "def") == "hello"


def test_allget_returns_independent_copy(tmp_path):
    default_dic = {"count": "5"}
    type_dic = {"count": int}
    cm = make_manager(tmp_path, default_dic, type_dic)

    snapshot = cm.allget()
    snapshot["count"] = 0
    assert cm.get("count") != 0


def test_env_var_override_on_reload(tmp_path, monkeypatch):
    cm = make_manager(tmp_path, {"name": "app"}, filename="cfg2.ini")
    assert cm.get("name") == "app"

    monkeypatch.setenv("NAME", "env_name")
    cm.reload()

    assert cm.get("name") == "env_name"
