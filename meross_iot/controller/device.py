from __future__ import annotations

import logging
from typing import List, Union, Optional

from meross_iot.model.enums import OnlineStatus, Namespace
from meross_iot.model.http.device import HttpDeviceInfo
from meross_iot.model.push.generic import GenericPushNotification

_LOGGER = logging.getLogger(__name__)


class BaseDevice(object):
    def __init__(self, device_uuid: str,
                 manager,  # TODO: type hinting "manager"
                 **kwargs):
        self._uuid = device_uuid
        self._manager = manager
        self._channels = self._parse_channels(kwargs.get('channels', []))

        # Information about device
        self._name = kwargs.get('devName')
        self._type = kwargs.get('deviceType')
        self._fwversion = kwargs.get('fmwareVersion')
        self._hwversion = kwargs.get('hdwareVersion')
        self._online = OnlineStatus(kwargs.get('onlineStatus', -1))

        # TODO: decide how to handle this
        self._abilities = None

    @property
    def internal_id(self) -> str:
        return f"#BASE:{self._uuid}"

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def name(self) -> str:
        return "unknown" if self._name is None else self._name

    @property
    def type(self) -> str:
        return "unknown" if self._type is None else self._type

    @property
    def firmware_version(self) -> str:
        return "unknown" if self._fwversion is None else self._fwversion

    @property
    def hardware_version(self) -> str:
        return "unknown" if self._hwversion is None else self._hwversion

    @property
    def online_status(self) -> OnlineStatus:
        return self._online

    @property
    def channels(self) -> List[ChannelInfo]:
        return self._channels

    def update_from_http_state(self, hdevice: HttpDeviceInfo) -> None:
        # TODO: update local name/hwversion/fwversion/online-status from online http information
        # Careful with online  status: not all the devices might expose an online mixin.
        raise Exception("Not implemented yet!")

    def handle_push_notification(self, namespace: Namespace, data: dict) -> bool:
        # By design, the base class does not implement any push notification.
        _LOGGER.debug(f"MerossBaseDevice {self.name} handling notification {namespace}")
        return False

    def handle_update(self, namespace: Namespace, data: dict) -> bool:
        # By design, the base class doe snot implement any update logic
        # TODO: we might update name/uuid/other stuff in here...
        return False

    async def async_update(self, *args, **kwargs) -> None:
        # TODO: check if this is still holding...
        """
        # This method should be overridden implemented by mixins and never called directly. Its main
        # objective is to call the corresponding GET ALL command, which varies in accordance with the
        # device type. For instance, wifi devices use GET System.Appliance.ALL while HUBs use a different one.
        # Implementing mixin should never call the super() implementation (as it happens
        # with _handle_update) as we want to use only an UPDATE_ALL method.
        # However, we want to keep it within the MerossBaseDevice so that we expose a consistent
        # interface.
        raise NotImplementedError("This method should never be called on the BaseMerossDevice. If this happens,"
                                  "it means there is a device which is not being attached any update mixin."
                                  f"Contact the developer. Current object bases: {self.__class__.__bases__}")
        """
        pass

    async def _execute_command(self, method: str, namespace: Namespace, payload: dict, timeout: float = 5) -> dict:
        return await self._manager.async_execute_cmd(destination_device_uuid=self.uuid,
                                                     method=method,
                                                     namespace=namespace,
                                                     payload=payload,
                                                     timeout=timeout)

    def is_hub(self) -> bool:
        return False

    def __str__(self) -> str:
        basic_info = "%s (%s, HW %s, FW %s): " % (
            self.name,
            self.type,
            self.hardware_version,
            self.firmware_version
        )

        return basic_info

    @staticmethod
    def _parse_channels(channel_data: List) -> List[ChannelInfo]:
        res = []
        if channel_data is None:
            return res

        for i, val in enumerate(channel_data):
            name = val.get('name')
            type = val.get('type')
            master = i == 0
            res.append(ChannelInfo(index=i, name=name, channel_type=type, is_master_channel=master))

        return res

    def lookup_channel(self, channel_id_or_name: Union[int, str]):
        res = []
        if isinstance(channel_id_or_name, str):
            res = list(filter(lambda c: c.name == channel_id_or_name, self._channels))
        elif isinstance(channel_id_or_name, int):
            res = list(filter(lambda c: c.index == channel_id_or_name, self._channels))
        if len(res) == 1:
            return res[0]
        raise ValueError(f"Could not find channel by id or name = {channel_id_or_name}")


class HubDevice(BaseDevice):
    # TODO: provide meaningful comment here describing what this class does
    #  Discvoery?? Bind/unbind?? Online??
    def __init__(self, device_uuid: str, manager, **kwargs):
        super().__init__(device_uuid, manager, **kwargs)
        self._sub_devices = {}

    def get_subdevices(self) -> List[GenericSubDevice]:
        raise NotImplementedError("TODO!")

    def get_subdevice(self, subdevice_id: str) -> Optional[GenericSubDevice]:
        return self._sub_devices.get(subdevice_id)

    def register_subdevice(self, subdevice: GenericSubDevice) -> None:
        # If the device is already registed, skip it
        if subdevice.subdevice_id in self._sub_devices:
            _LOGGER.error(f"Subdevice {subdevice.subdevice_id} has been already registered to this HUB ({self.name})")
            return

        self._sub_devices[subdevice.subdevice_id] = subdevice


class GenericSubDevice(BaseDevice):
    def __init__(self, hubdevice_uuid: str, subdevice_id: str, manager, **kwargs):
        super().__init__(hubdevice_uuid, manager, **kwargs)
        self._subdevice_id = subdevice_id
        self._type = kwargs.get('subDeviceType')
        self._name = kwargs.get('subDeviceName')
        self._onoff = None
        self._mode = None
        self._temperature = None
        hub = manager.find_device(uuids=(hubdevice_uuid,))
        if len(hub) < 1:
            raise ValueError("Specified hub device is not present")
        self._hub = hub[0]

    async def _execute_command(self, method: str, namespace: Namespace, payload: dict, timeout: float = 5) -> dict:
        # Every command should be invoked via HUB?
        raise NotImplementedError("TODO!")

    async def async_update(self, *args, **kwargs) -> None:
        # For subdevices, the
        await self._hub.async_update(subdevice_ids=(self._subdevice_id,))

    @property
    def internal_id(self) -> str:
        return f"#BASE:{self._uuid}#SUB:{self._subdevice_id}"

    @property
    def subdevice_id(self):
        return self._subdevice_id

    @property
    def online_status(self) -> OnlineStatus:
        # If the HUB device is offline, return offline
        if self._hub.online_status != OnlineStatus.ONLINE:
            return self._hub.online_status

        return self._online


class ChannelInfo(object):
    def __init__(self, index: int, name: str = None, channel_type: str = None, is_master_channel: bool = False):
        self._index = index
        self._name = name
        self._type = channel_type
        self._master = is_master_channel

    @property
    def index(self) -> int:
        return self._index

    @property
    def is_usb(self) -> bool:
        return self._type == 'USB'

    @property
    def is_master_channel(self) -> bool:
        return self._master

