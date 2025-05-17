from .com import log_decorator,CustomLogger
from .configmanager import ConfigManager
from .slackapi import textpost,imagepost,imagepost_from_url

__version__ = '0.1.2'

__all__ = [
    'log_decorator',
    'CustomLogger',
    'ConfigManager',
    'textpost',
    'imagepost',
    'imagepost_from_url',
    # __version__ は通常 __all__ に含めませんが、アクセスしたい場合は含めることもあります
]

__author__  = "Sutachi Agemame <sutachiagemame@gmail.com>"
__status__  = "production"
__version__ = "0.1.2"
__date__    = "2025/05/18"
