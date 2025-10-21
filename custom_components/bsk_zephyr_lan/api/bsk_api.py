import re, json

from enum import Enum
from http import HTTPStatus

from aiohttp import ClientResponseError, ContentTypeError
from aiohttp.client import ClientResponse, ClientSession
from pydantic import BaseModel

class ZephyrException(Exception):
    """Base class for Zephyr exceptions"""

class InvalidAuthError(ZephyrException):
    """Invalid authentication"""    


class FanMode(str, Enum):
    cycle = "cycle"
    extract = "extract"
    supply = "supply"


class FanSpeed(int, Enum):
    night = 22
    low = 30
    medium = 55
    high = 80


class ZephyrDevice(BaseModel):
    _id: str
    group_id: str
    group_title: str
    updated_at: str

    device_id: str
    device_version: str
    device_model: str
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
    
    humidity_boost_level: int
    humidity_boost_state: bool

    buzzer: bool

    filter_timer: int
    hygiene_status: int



class BSKZephyrLanClient:
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
            r.raise_for_status()
            return await r.json()


    async def login(self) -> str:
        #no auth required, try to load device info
        await self.list_devices()

    def _parse_value(self, key: str, value: str):
        self._last_value_unit = None
        """Converte stringhe in numeri quando possibile"""
        v = value.strip()
        if key in ('power', 'buzzer', 'humidity_boost_state'):
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
        # altrimenti stringa
        return v

    async def fetch_device_data(self):
        #for now data are only in html
        self._raw_html = self._get("", asText=True)
        # Find all tuple <b>Key:</b> Value
        pattern =  r"<p><b>([^<:]+):<\/b>(.*?)<\/p>"
        matches = re.findall(pattern, self._raw_html)
        for okey, value in matches:
            # Convert 'Fan Speed' -> 'fan_speed'
            key = okey.strip().lower().replace(" ", "_")
            if key in ('ssid', 'rssi', 'ip'):
                key = f"wifi_{key}"
            if key in ('version', 'model'):
                key = f"device_{key}"
            if (key == "set_humidity"):
                key = "humidity_boost_level"
            if (key == "humidity_boost"):
                key = "humidity_boost_state"
            self._raw_data[key] = self._parse_value(key, value)
            if self._last_value_unit:
                self._raw_data[f"{key}_unit"] = self._last_value_unit

    async def list_devices(self) -> list[ZephyrDevice]:
        try:
            await self.fetch_device_data()

            data = self._raw_data
            data["_id"] = data["device_id"]
            data["group_id"] = data["device_id"]
            data["group_title"] = data["device_model"]
            data["updated_at"] = datetime.utcnow().isoformat()
            data["fan_speed_enum"] = min(FanSpeed, key=lambda fs: abs(fs.value - data["fan_speed"]))
            data["operation_mode_enum"] = parse_fan_mode(data["operation_mode"])

            # Crea istanza Pydantic
            models = []
            models.append(ZephyrDevice(**data))
            return models
        except ClientResponseError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise InvalidAuthError(err)
            else:
                raise ZephyrException(err)

    async def control_device(
        self,
        groupID: str,
        power: bool | None = None,
        operation_mode_enum: FanMode | None = None,
        fan_speed_enum: FanSpeed | None = None,
        humidity_boost_level: int | None = None,
        buzzer: bool | None = None,
    ):
        try:
            if power is not None:
                await self._post("/on" if power else "/off")
            if operation_mode_enum == FanMode.cycle:
                await self._post("/cycle")
            if operation_mode_enum == FanMode.supply:
                await self._post("/intake")
            if operation_mode_enum == FanMode.extract:
                await self._post("/exhaust")
            if fan_speed_enum:
                await self._post("/fan", {"speed": int(fan_speed_enum)})
            if humidity_boost_level is not None:  # allow 0
                await self._post("/humid", {"level": humidity_boost_level})
            if buzzer is not None:
                await self._post("/buzzer", {"state": 1 if buzzer else 0})

        except ClientResponseError as err:
            raise ZephyrException from err

def to_bool(value: str) -> bool:
    v = str(value).strip().lower()
    return v in ("1", "true", "on", "yes")


def parse_fan_mode(value: str) -> FanMode:
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
    return FanMode.cycle  # default