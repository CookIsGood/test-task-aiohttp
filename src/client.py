import aiohttp
import asyncio
import argparse
import re
import json
import logging

from dataclasses import dataclass
from typing import Union, Tuple
from collections import defaultdict
from aiohttp.client_exceptions import ClientConnectorError
from enum import Enum


@dataclass
class Command:
    command: str
    metadata: Union[float, None] = None


class LampException(Exception):
    pass


class AppException(Exception):
    pass


class LampState(Enum):
    ON = "ON"
    OFF = "OFF"


class Lamp:
    def __init__(self, state: LampState = LampState.OFF, color: float = 10.0) -> None:
        self.state = state
        self.color = color
        self._logger = logging.getLogger('app_logger')

    def _turn_on(self, value=None) -> None:
        """
        Method for turn on lamp

        :param value:
        :return:
        """
        if value is not None:
            raise LampException("For command ON field metadata must be None")
        self.state = self.state.ON
        self._logger.debug("Lamp turned ON")

    def _turn_off(self, value=None) -> None:
        """
        Method for turn off lamp

        :param value:
        :return:
        """
        if value is not None:
            raise LampException("For command OFF field metadata must be None")
        self.state = self.state.OFF
        self._logger.debug("Lamp turned OFF")

    def _switch_color(self, color_value: float) -> None:
        """
        Method for switch lamp color

        :param color_value: Raw color value
        :return:
        """
        valid_color = self._validate_color(color_value)
        if self.state.value == "OFF":
            raise LampException("Can not change lamp color when lamp is turned off")
        else:
            self.color = valid_color
        self._logger.debug(f"Lamp color is {valid_color}")

    @staticmethod
    def _validate_color(value: float) -> float:
        """
        Method for validate lamp color

        :param value: Raw color value
        :return: Validated color value
        """
        if value >= 0:
            return value
        raise LampException("Invalid value for color!")


class CommandHandler:
    def __init__(self) -> None:
        self._lamp = Lamp()
        self._logger = logging.getLogger('app_logger')

    def dispatch(self, command: Command) -> None:
        """
        Method for executing lamp commands

        :param command: Command to be executed
        :return:
        """
        commands = {
            "ON": self._lamp._turn_on,
            "OFF": self._lamp._turn_off,
            "COLOR": self._lamp._switch_color
        }
        function = commands.get(command.command, None)
        if function is None:
            self._logger.info(f"Command {command.command} not found!")
            return None
        try:
            if command.metadata is not None:
                function(command.metadata)
            else:
                function()
        except LampException as error:
            self._logger.warning(error)


class App:
    def __init__(self) -> None:
        self._command_handler = CommandHandler()
        logging.basicConfig(
            level=logging.DEBUG
        )
        self._logger = logging.getLogger('app_logger')

    async def _start_client(self, host: str, port: int) -> None:
        """
        Method for start async client

        :param host: Server IP address
        :param port: Server port
        :return:
        """
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector()) as session:
            async with session.ws_connect(f'http://{host}:{port}') as ws:
                while True:
                    try:
                        data = input("Enter data: \n")
                        await ws.send_str(data)
                        receive_raw = await ws.receive()
                        command = self._parse_message(receive_raw.data)
                        if command.command == "QUIT":
                            break
                        self._command_handler.dispatch(command=command)
                    except AppException as e:
                        self._logger.error(e)
        self._logger.info("Client session was been closed")

    @staticmethod
    def _parse_message(raw_data: str) -> Command:
        """
        Method for parse command message

        :param raw_data: raw json string
        :return: Command object
        """

        try:
            data = json.loads(raw_data)
        except:
            raise AppException("Error serialize json to dictionary!")
        data = defaultdict(lambda: None, data)
        if data["command"] is None or not isinstance(data["command"], str):
            raise AppException("Error field command not must being None or not str")
        if data["metadata"] is not None and not isinstance(data["metadata"], float):
            raise AppException("Error field metadata not must being not float")
        return Command(command=data["command"], metadata=data["metadata"])

    def run(self):
        """Main method for run app"""
        try:
            parser = argparse.ArgumentParser()
            parser.add_argument("--uri", type=self._validate_uri, default="127.0.0.1:9999",
                                required=False, help="Fill socket for connect lamp server")
            args = parser.parse_args()
        except Exception as e:
            self._logger.error(e)
        try:
            asyncio.run(self._start_client(args.uri[0], args.uri[1]))
        except ClientConnectorError as e:
            self._logger.error(e)

    @staticmethod
    def _validate_uri(value: str) -> Tuple[str, int]:
        """
        Validate uri string from CLI

        :param value: Raw uri
        :return: Tuple(IP, PORT)
        """

        result = re.match(
            r"\b((?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))"
            r":(\d+)\b", value)
        if result is None:
            raise argparse.ArgumentTypeError(f"String {value} include not accepted format!")
        ip_address = result.group(1)
        port = int(result.group(2))
        if not (0 < port <= 65535):
            raise argparse.ArgumentTypeError(f"Selected port must be in range (0, 65535)")
        return ip_address, port