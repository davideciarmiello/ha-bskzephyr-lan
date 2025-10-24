import re, json
import logging

from enum import Enum
from http import HTTPStatus
from datetime import datetime
from packaging import version

from aiohttp import ClientResponseError, ContentTypeError
from aiohttp.client import ClientResponse, ClientSession
from pydantic import BaseModel

_LOGGER = logging.getLogger(__name__)

class ZephyrException(Exception):
    """Base class for Zephyr exceptions"""

class InvalidAuthError(ZephyrException):
    """Invalid authentication"""    


class FanMode(str, Enum):
    supply = "supply"
    cycle = "cycle"
    extract = "extract"


class FanSpeed(str, Enum):
    night = "night"
    low = "low"
    medium = "medium"
    high = "high"


class ZephyrDevice(BaseModel):
    _id: str
    group_id: str
    group_title: str
    updated_at: str

    device_id: str
    device_version: str
    device_model: str
    device_name: str
    wifi_ssid: str
    wifi_rssi: int
    wifi_ip: str

    power: bool #old deviceStatus
    fan_speed: int
    fan_speed_enum: FanSpeed
    temperature: float
    temperature_unit: str

    humidity: float
    operation_mode: str
    operation_mode_enum: FanMode
    
    humidity_boost_enabled: bool
    humidity_boost_level: int
    humidity_boost_running: bool

    buzzer: bool

    filter_timer: int
    hygiene_status: int



class BSKZephyrLanClient:
    HUMID_BOOST_DISABLED_LEVEL = 99

    def __init__(
        self,
        session: ClientSession,
        host: str | None = None,
    ) -> None:
        self._aiohttp_session: ClientSession = session
        self._host = host
        self._host_url = f"http://{host}"
        self._raw_html = ""
        self._raw_data = {}
        self._device = None
        self.persistent_data = {}


    async def _get(self, path, headers=None, params=None, asText=True):
        url = self._host_url + path
        async with self._aiohttp_session.get(url, headers=headers, **(params or {})) as r:
            r.raise_for_status()
            if asText:
                return await r.text()
            return await r.json()

    async def _post(self, path, data=None, headers=None, params=None):
        url = self._host_url + path
        async with self._aiohttp_session.post(url, data=data, headers=headers, **(params or {})) as r:
            if r.status >= 400:
                text = await r.text()
                raise Exception(f"HTTP {r.status} on {url}. Data: {data}. Response: {text}")
            if path == "/off":
                self._raw_data["humidity_boost_running"] = False
            return await r.json()


    async def login(self) -> str:
        #no auth required, try to load device info
        await self.list_devices()

    def _parse_value(self, key: str, value: str):
        self._last_value_unit = None
        """Converte stringhe in numeri quando possibile"""
        v = value.strip()
        if key in ('power', 'buzzer', 'humidity_boost_running'):
            return to_bool(v)
        for unit in ["°C", "°F", "%", "dBm", "h"]:
            if v.endswith(unit) and v.endswith(f" {unit}"):
                try:                    
                    numeric_part = float(v.replace(unit, "").strip())
                    if unit in ("h"):
                        numeric_part = int(numeric_part)
                    self._last_value_unit = unit
                    return numeric_part
                except ValueError:
                    return v
                break
        if key in ('fan_speed', 'humidity_boost_level', 'humidity_boost_level_raw', 'hygiene_status'):
            try:                    
                return int(v)
            except ValueError:
                return v
        # altrimenti stringa
        return v

    async def fetch_device_data(self):
        #for now data are only in html
        try:
            self._raw_html = await self._get("", asText=True)
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise InvalidAuthError(err)
            else:
                raise ZephyrException(err)
        # Find all tuple <b>Key:</b> Value
        pattern =  r"<p><b>([^<:]+):<\/b>(.*?)<\/p>"
        matches = re.findall(pattern, self._raw_html)
        valid = False
        for okey, value in matches:
            # Convert 'Fan Speed' -> 'fan_speed'
            key = okey.strip().lower().replace(" ", "_")
            if key in ('ssid', 'rssi', 'ip'):
                key = f"wifi_{key}"
            if key in ('version', 'model'):
                key = f"device_{key}"
            if (key == "set_humidity"):
                key = "humidity_boost_level_raw"
                self._raw_data["humidity_boost_enabled"] = None
            if (key == "humidity_boost"):
                key = "humidity_boost_running"
            self._raw_data[key] = self._parse_value(key, value)
            if self._last_value_unit:
                self._raw_data[f"{key}_unit"] = self._last_value_unit
            if key in ("fan_speed", "operation_mode"):
                self._raw_data[f"{key}_enum"] = None
                valid = True
        if not valid:
            raise Exception(f"No valid data received: {self._raw_html}")

    async def list_devices(self, from_cache: bool = False) -> dict[str, ZephyrDevice]:
        try:
            if not from_cache:
                await self.fetch_device_data()
            data = self._raw_data
            if not "device_name" in data:
                data["_id"] = data["device_id"]
                data["group_id"] = data["device_id"] + "_group"
                data["group_title"] = data["device_model"]
                data["device_name"] = data["device_model"]
                if data["device_name"] == "BSK-Zephyr-160MM-V2_4MB":
                    data["device_name"] = "BSK-Zephyr"
                if "BSK-Zephyr-Mini" in data["device_name"]:
                    data["device_name"] = "BSK-Zephyr-Mini"
            data["updated_at"] = datetime.utcnow().isoformat()
            data["fan_speed_enum"] = fan_speed_value_to_enum(int(data["fan_speed"]))
            data["operation_mode_enum"] = parse_fan_mode(data["operation_mode"])

            self.persistent_data["humidity_boost_level_max"] = self.HUMID_BOOST_DISABLED_LEVEL - 1

            #save or restore the last value
            data["humidity_boost_enabled"] = data.get("humidity_boost_level_raw", 100) < self.HUMID_BOOST_DISABLED_LEVEL
            if data["humidity_boost_enabled"]:
                data["humidity_boost_level"] = data["humidity_boost_level_raw"]
                self.persistent_data["humidity_boost_level_last"] = data["humidity_boost_level_raw"]
            else:
                data["humidity_boost_level"] = self.persistent_data.get("humidity_boost_level_last", 60)

            # Crea istanza Pydantic
            self._device = ZephyrDevice(**data)
            models = {}
            models[self._device.group_id] = self._device
            return models
        except Exception as err:
            _LOGGER.exception("Error in list_devices")
            raise

    async def control_device(
        self,
        groupID: str,
        power: bool | None = None,
        operation_mode_enum: FanMode | str | None = None,
        fan_speed: int | None = None,
        fan_speed_enum: FanSpeed | str | None = None,
        humidity_boost_enabled: bool | None = None,
        humidity_boost_level: int | None = None,
        buzzer: bool | None = None,
    ):
        #try:
            if power is not None:
                await self._post("/on" if power else "/off")
                self._raw_data["power"] = power
            if operation_mode_enum:
                await self._set_operation_mode(groupID, operation_mode_enum)
            if fan_speed_enum:
                if isinstance(fan_speed_enum, str):
                    fan_speed_enum = parse_fan_speed(fan_speed_enum)
                fan_speed = fan_speed_to_speed_value(fan_speed_enum)
            if fan_speed:
                await self._post("/fan", {"speed": fan_speed})
                self._raw_data["fan_speed"] = fan_speed
            if humidity_boost_enabled == True:
                level = int(self._raw_data.get("humidity_boost_level", 60))
                await self._set_humidity_boost_level(groupID, level)
            if humidity_boost_enabled == False:
                await self._set_humidity_boost_level(groupID, self.HUMID_BOOST_DISABLED_LEVEL)
            if humidity_boost_level is not None:
                if humidity_boost_level >= self.HUMID_BOOST_DISABLED_LEVEL:
                    raise Exception(f"humidity_boost_level value {humidity_boost_level} not allowed. Max is {self.HUMID_BOOST_DISABLED_LEVEL - 1}")
                if self._raw_data["humidity_boost_enabled"]:
                    await self._set_humidity_boost_level(groupID, humidity_boost_level)
                else:
                    self.persistent_data["humidity_boost_level_last"] = humidity_boost_level
            if buzzer is not None:
                await self._post("/buzzer", {"state": 1 if buzzer else 0})
                self._raw_data["buzzer"] = buzzer


        #except ClientResponseError as err:
        #    raise ZephyrException from err
    def _check_version(self, v):
        return version.parse(self._raw_data["device_version"]) <= version.parse(v)
    
    
    async def _set_operation_mode(self, groupID: str, mode: FanMode | str):
        if isinstance(mode, str):
            mode = parse_fan_mode(mode)
        if mode == FanMode.cycle:
            await self._post("/cycle")
            self._raw_data["operation_mode"] = "cycle"
        if mode == FanMode.supply:
            await self._post("/intake")
            self._raw_data["operation_mode"] = "intake"
        if mode == FanMode.extract:
            await self._post("/exhaust")
            self._raw_data["operation_mode"] = "exhaust"


    async def _set_humidity_boost_level(self, groupID: str, level: int):
        await self._post("/humid", {"level": level})
        self._raw_data["humidity_boost_level_raw"] = level
        #version 3.1.5 bug changing humidy set point, not stop boost_running
        if (self._raw_data["humidity_boost_running"]
            and self._check_version("3.1.5") and self._raw_data["power"]
            and level > self._raw_data["humidity"]):
            await self._post("/off")
            await self._post("/on")

    

def to_bool(value: str) -> bool:
    if value == "0":
        return False
    if value == "1":
        return True
    v = str(value).strip().lower()
    return v in ("1", "true", "on", "yes")


def fan_speed_to_speed_value(speed: FanSpeed) -> int:
    if speed == FanSpeed.high:
        return 80
    if speed == FanSpeed.medium:
        return 55
    if speed == FanSpeed.low:
        return 30
    return 22        

def fan_speed_value_to_enum(speed: int) -> FanSpeed:
    if (speed >= 80):
        return FanSpeed.high
    if (speed >= 55):
        return FanSpeed.medium
    if (speed >= 30):
        return FanSpeed.low
    if (speed >= 22):
        return FanSpeed.night
    return FanSpeed.night

def parse_fan_speed(speed: str, raiseError = True) -> FanSpeed:
    for mode in FanSpeed:
        if speed == mode.value or speed == mode.name:
            return mode
    v = speed.strip().lower()  # normalizza input
    for mode in FanSpeed:
        if v == mode.value.lower() or v == mode.name.lower():
            return mode
    if raiseError:
        raise Exception(f"Option {speed} is not valid for FanSpeed, valid options are: {[m.name for m in FanSpeed]}")
    return None

def parse_fan_mode(value: str, raiseError = True) -> FanMode:
    """
    Converte una stringa in FanMode enum.
    Se non corrisponde, ritorna un default (cycle).
    """
    v = value.strip().lower()  # normalizza input
    if v == "cycle":
        return FanMode.cycle
    if v in ("intake", "supply"):
        return FanMode.supply
    if v in ("exhaust", "extract"):
        return FanMode.extract
    for mode in FanMode:
        if v == mode.value:
            return mode    
    if raiseError:
        raise Exception(f"Option {value} is not valid for FanMode, valid options are: {[m.name for m in FanMode]}")
    return None