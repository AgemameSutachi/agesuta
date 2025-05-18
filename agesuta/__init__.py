from .com import log_decorator,CustomLogger
from .configmanager import ConfigManager
from .slackapi import SlackPoster

__all__ = [
    'log_decorator',
    'CustomLogger',
    'ConfigManager',
    'SlackPoster',
]

with open("version.txt","r") as f:
    version=f.read().replace("\n","")
    
with open("date.txt","r") as f:
    date=f.read().replace("\n","")

__author__  = "Sutachi Agemame <sutachiagemame@gmail.com>"
__status__  = "production"
__version__ = version
__date__    = date
