from .com import log_decorator, CustomLogger
from .configmanager import ConfigManager
from .slackapi import SlackPoster
from .secretmask import (
    mask_secret,
    mask_secrets_in_text,
    count_secrets_in_text,
    count_masked_in_text,
    install_secret_mask,
)
import os

__all__ = [
    "log_decorator",
    "CustomLogger",
    "ConfigManager",
    "SlackPoster",
    "mask_secret",
    "mask_secrets_in_text",
    "count_secrets_in_text",
    "count_masked_in_text",
    "install_secret_mask",
]

_package_dir = os.path.dirname(__file__)
version_file_path = os.path.join(_package_dir, "version.txt")
date_file_path = os.path.join(_package_dir, "date.txt")

if os.path.exists(version_file_path):
    with open(version_file_path, "r") as f:
        version = f.read().replace("\n", "")
else:
    version = None

if os.path.exists(date_file_path):
    with open(date_file_path, "r") as f:
        date = f.read().replace("\n", "")
else:
    date = None

__author__ = "Sutachi Agemame <sutachiagemame@gmail.com>"
__status__ = "production"
__version__ = version
__date__ = date
