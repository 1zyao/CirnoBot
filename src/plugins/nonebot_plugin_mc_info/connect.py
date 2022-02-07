import threading

import asyncio
import json
import time
from functools import wraps

import websockets
from websockets.exceptions import ConnectionClosedError, InvalidStatusCode
import nonebot
import httpx


class MinecraftConnector:
    listener_dict = {
        'on_player_chat': [],
        'on_player_login': [],
        'on_player_disconnected': [],
        'on_player_execute_command': []
    }

    def __init__(self, server_uri: str, auth_key: str):
        self.server_uri = server_uri
        self.auth_key = auth_key
        self.server_info = None
        self.connected = True
        self.player_chat = []
        self.command_list = []
        self.login_event = []
        self.logout_event = []
        self.players = []
        if not self.test_connection():
            self.connected = False
            self.server_info = self.get_server_info()
            self.ws_tread = self.WebSocketThread(self._ws_connect)
            self.ws_tread.start()
        else:
            self.server_info = self.get_server_info()
            self.ws_tread = self.WebSocketThread(self._ws_connect)
            self.ws_tread.start()
            nonebot.logger.opt(colors=True).success(f"<g>与服务器: {server_uri}的ping test成功！</g>")

    def get_server_name(self):
        if self.server_info:
            return self.server_info["name"]
        else:
            return "Server disconnected"

    async def get_uuid_from_name(self, name):
        for player in self.players:
            if player["Name"].lower() == name.lower():
                return player["uuid"]
        self.players = await self.get_all_players()
        for player in self.players:
            if player["Name"].lower() == name.lower():
                return player["uuid"]
        return None

    async def get_name_from_uuid(self, uuid: str) -> str:
        for player in self.players:
            if player["uuid"] == uuid:
                return player["Name"]
        self.players = await self.get_all_players()
        for player in self.players:
            if player["uuid"] == uuid:
                return player["Name"]
        raise ValueError

    async def process_player_chat(self, message) -> dict:
        send_time = message["timestampMillis"]
        message = message["message"]
        player_name = message.split(" ")[0].replace('<', '').replace('>', '')
        message_content = message[:-3].replace(f"<{player_name}> ", "") if "[m" in message else message.replace(f"<{player_name}> ", "")
        player_uuid = await self.get_uuid_from_name(player_name)
        return {
            "name": player_name,
            "message": message_content,
            "uuid": player_uuid,
            "time": send_time
        }

    async def process_commands(self, message) -> dict:
        message = message["message"]
        player_name = message.split(" ")[0]
        command_content = message.split(" ")[-1].replace("/", "")
        player_uuid = await self.get_uuid_from_name(player_name)
        return {
            "name": player_name,
            "command": command_content,
            "uuid": player_uuid
        }

    class WebSocketThread(threading.Thread):
        def __init__(self, fun):
            self.fun = fun
            threading.Thread.__init__(self)

        def run(self):
            asyncio.run(self.fun())

    @classmethod
    def handle(cls, listener_type: str):
        def _handle(func):
            cls.listener_dict[listener_type].append(func)

            @wraps(func)
            def wrapper(*args, **kwargs):
                rs = func(*args, **kwargs)
                return rs

            return wrapper

        return _handle

    async def _ws_connect(self):
        while True:
            try:
                async with websockets.connect(f"ws://{self.server_uri}/v1/ws/console",
                                              extra_headers={"Cookie": f"x-servertap-key={self.auth_key}"}
                                              ) as websocket:
                    nonebot.logger.opt(colors=True).success(f"<g>与服务器: {self.server_uri}的Websocket连接建立成功...</g>")
                    self.connected = True
                    while True:
                        log = await websocket.recv()
                        message = json.loads(log)
                        if int(round(time.time() * 1000)) - message["timestampMillis"] > 10000:
                            # 超过5s的记录将不会执行
                            continue
                        if message['loggerName'] == 'net.minecraft.server.players.PlayerList' and "logged in" in message["message"]:
                            self.login_event.append(message)
                            for listener in self.listener_dict['on_player_login']:
                                await listener(message=message, server=self)
                        elif message['loggerName'] == 'net.minecraft.server.network.PlayerConnection' and 'Disconnected' in message['message']:
                            self.logout_event.append(message)
                            for listener in self.listener_dict['on_player_disconnected']:
                                await listener(message=message, server=self)
                        elif message['message'].startswith('<'):
                            self.player_chat.append(await self.process_player_chat(message))
                            for listener in self.listener_dict['on_player_chat']:
                                await listener(message=message, server=self)
                        elif 'issued server command' in message['message']:
                            self.command_list.append(message)
                            for listener in self.listener_dict['on_player_execute_command']:
                                await listener(message=message, server=self)
            except ConnectionClosedError as e:
                self.connected = False
                nonebot.logger.opt(colors=True).warning(f"<y>服务器: {self.server_uri}关闭连接(可能原因：服务器被关闭), 将在10秒后重试...</y>")
                await asyncio.sleep(10)
            except ConnectionRefusedError as e:
                self.connected = False
                nonebot.logger.opt(colors=True).warning(f"<y>服务器: {self.server_uri}连接被拒绝(可能原因：服务器未开启，插件端口配置错误), 将在10秒后重试...</y>")
                await asyncio.sleep(10)
            except InvalidStatusCode as e:
                nonebot.logger.opt(colors=True).warning(
                    f"<y>服务器: {self.server_uri}连接404(可能原因：服务器未开启，插件端口配置错误), 将在10秒后重试...</y>")
                await asyncio.sleep(10)

    def test_connection(self) -> bool:
        try:
            httpx.get(f"http://{self.server_uri}/v1/ping", headers={"key": self.auth_key})
            return True
        except httpx.RequestError:
            if self.connected and self.connected:
                nonebot.logger.opt(colors=True).warning(
                    f"<y>Connect to Minecraft server: {self.server_uri} failed! Please check config.</y>")
            return False

    async def get_server_info(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/server", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_players(self) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/players", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_worlds(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/worlds", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_specific_worlds(self, world_uuid):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/worlds/{world_uuid}",
                                        headers={"key": self.auth_key})
            return json.loads(response.text)

    async def save_world(self, world_uuid):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://{self.server_uri}/v1/worlds/{world_uuid}/save",
                                         headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_score_board(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/scoreboard", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_specific_score_board(self, name: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/scoreboard/{name}",
                                        headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_ops(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/ops", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def set_op(self, name):
        response = await self.execute_command(f"op {name}")
        return response

    async def remove_op(self, name):
        response = await self.execute_command(f"deop {name}")
        return response

    async def get_all_players(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/players/all", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_inventory(self, player_uuid, world_uuid):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/players/{player_uuid}/{world_uuid}/inventory",
                                        headers={"key": self.auth_key})
            return json.loads(response.text)

    async def broadcast(self, message: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://{self.server_uri}/v1/chat/broadcast", headers={"key": self.auth_key},
                                         data={"message": message})
            return json.loads(response.text)
        # response = await self.execute_command(f"say {message}")
        # return response

    async def tell(self, player_uuid, message: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://{self.server_uri}/v1/chat/tell", headers={"key": self.auth_key},
                                         data={"playerUuid": player_uuid, "message": message})
            return json.loads(response.text)

    async def get_plugins(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/plugins", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def get_white_list(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{self.server_uri}/v1/server/whitelist", headers={"key": self.auth_key})
            return json.loads(response.text)

    async def white_list_on(self):
        response = await self.execute_command("whitelist on")
        return response

    async def white_list_off(self):
        response = await self.execute_command("whitelist off")
        return response

    async def add_white_list(self, name):
        response = await self.execute_command(f"whitelist add {name}")
        return response

    async def remove_white_list(self, name):
        response = await self.execute_command(f"whitelist remove {name}")
        return response

    async def execute_command(self, command: str, time: int = 100000):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"http://{self.server_uri}/v1/server/exec", headers={"key": self.auth_key},
                                             data={
                                                 "command": command,
                                                 "time": time
                                             })
                return response.text
            except httpx.ReadTimeout as e:
                return {'msg': "this command has no return"}

    async def placeholder_api(self, message, uuid=None):
        async with httpx.AsyncClient() as client:
            if uuid:
                data = {
                    'message': message,
                    'uuid': uuid
                }
            else:
                data = {
                    'message': message
                }
            response = await client.post(f"http://{self.server_uri}/v1/placeholders/replace",
                                         headers={"key": self.auth_key},
                                         data=data)
            return json.loads(response.text)


