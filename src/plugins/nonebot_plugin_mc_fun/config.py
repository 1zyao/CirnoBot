from pydantic import BaseSettings
import os

current_folder = os.path.dirname(__file__)

default_config = {
    "server_uri": "",
    "server_address": "",
    "is_focus": [],
    "superuser": [],

    "enable_placeholder_api": False,
    "show_welcome_message": True,
    "welcome_message": "§6欢迎小伙伴%player%加入服务器～",
    "welcome_message_broadcast": "§6欢迎小伙伴%player%加入服务器～",

    "auto_reply": True,
    "auto_reply_dict": {"hello": "world"},
    "auto_reply_start": ".",

    "join_event_qq_broadcast": True,
    "join_event_qq_message": "小伙伴%player%加入服务器%server_name%了哦～当前服务器人数%player_num%人",
    "join_event_qq_broadcast_group": [],

    "leave_event_qq_broadcast": True,
    "leave_event_qq_message": "小伙伴%player%离开服务器了呢～当前服务器人数%player_num%人哦",
    "leave_event_qq_broadcast_group": [],

    "command_translator": True,
    "translate_commands": {"say": "say helloworld"},

    "server_status_display": True,

    "player_search": True,

    "white_list": True,
    "white_list_players": {},

    "allow_message_transfer": True,

    "op": True,

    "server_command": True,

}


class Config(BaseSettings):
    # Your Config Here

    class Config:
        pass