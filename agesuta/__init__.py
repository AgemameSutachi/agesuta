from .com import log_decorator,CustomLogger
from .configmanager import ConfigManager
from .slackapi import SlackPoster
import os

__all__ = [
    'log_decorator',
    'CustomLogger',
    'ConfigManager',
    'SlackPoster',
]

_package_dir = os.path.dirname(__file__)
version_file_path = os.path.join(_package_dir, "version.txt")
date_file_path = os.path.join(_package_dir, "date.txt")

with open(version_file_path,"r") as f:
    version=f.read().replace("\n","")
    
with open(date_file_path,"r") as f:
    date=f.read().replace("\n","")

__author__  = "Sutachi Agemame <sutachiagemame@gmail.com>"
__status__  = "production"
__version__ = version
__date__    = date
