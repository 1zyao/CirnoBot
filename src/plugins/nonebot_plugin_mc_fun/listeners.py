from ..nonebot_plugin_mc_info import MinecraftConnector
from .data_source import get_config
from .util import safe_send
from nonebot.plugin import require
from .util import message_preprocess
plugin_mc_info = require('nonebot_plugin_mc_info')


@MinecraftConnector.handle('on_player_chat')
async def _chat_event(message, server: MinecraftConnector):
    message_info = await server.process_player_chat(message)
    configs = get_config()
    for config in configs:
        if server.server_uri == config["server_uri"] and config["auto_reply"]:
            if message_info["message"].startswith(config["auto_reply_start"]):
                message_info["message"] = message_info["message"][1:]
            else:
                break
            if message_info["message"] in config["auto_reply_dict"]:
                await server.tell(message_info["uuid"],
                                  await message_preprocess(
                                      message=config["auto_reply_dict"][message_info["message"]],
                                      uuid=message_info["uuid"],
                                      enable_placeholder_api=config["enable_placeholder_api"],
                                      server=server
                                  ))
                break


@MinecraftConnector.handle('on_player_login')
async def _login_event(message, server: MinecraftConnector):
    config_list = get_config()
    for config in config_list:
        if config["server_uri"] != server.server_uri:
            continue
        if config["show_welcome_message"]:
            broadcast_message = await message_preprocess(message=config["welcome_message_broadcast"],
                                                         server=server,
                                                         enable_placeholder_api=config["enable_placeholder_api"],
                                                         uuid=await server.get_uuid_from_name(message['message'].split('[')[0]))
            await server.broadcast(broadcast_message)
        if config["join_event_qq_broadcast"]:
            for group_id in config["join_event_qq_broadcast_group"]:
                group_message = await message_preprocess(message=config["join_event_qq_message"],
                                                         server=server,
                                                         enable_placeholder_api=config["enable_placeholder_api"],
                                                         uuid=await server.get_uuid_from_name(message['message'].split('[')[0]))
                await safe_send("group", group_id, group_message)
        if config["show_welcome_message"]:
            wel_message = await message_preprocess(message=config["welcome_message"],
                                                   server=server,
                                                   enable_placeholder_api=config["enable_placeholder_api"],
                                                   uuid=await server.get_uuid_from_name(message['message'].split('[')[0]))
            await server.tell(await server.get_uuid_from_name(message['message'].split('[')[0]), wel_message)


@MinecraftConnector.handle('on_player_disconnected')
async def _logout_event(message, server: MinecraftConnector):
    configs = get_config()
    for config in configs:
        if config["server_uri"] == server.server_uri:
            if config["leave_event_qq_broadcast"]:
                for group_id in config["leave_event_qq_broadcast_group"]:
                    group_message = await message_preprocess(message=config["leave_event_qq_message"],
                                                             server=server,
                                                             enable_placeholder_api=config["enable_placeholder_api"],
                                                             uuid=await server.get_uuid_from_name(
                                                                 message['message'].split(' ')[0]))
                    await safe_send("group", group_id, group_message)


@MinecraftConnector.handle('on_player_execute_command')
async def _execute_command(message, server: MinecraftConnector):
    configs = get_config()
    for config in configs:
        if server.server_uri == config["server_uri"]:
            if config["command_translator"]:
                command_info = await server.process_commands(message)
                if command_info["command"] in config["translate_commands"]:
                    await server.execute_command(
                        command=await message_preprocess(message=config["translate_commands"][command_info["command"]],
                                                         server=server,
                                                         enable_placeholder_api=config["enable_placeholder_api"],
                                                         uuid=await server.get_uuid_from_name(command_info["name"])))
