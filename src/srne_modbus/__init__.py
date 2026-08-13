"""srne-modbus — read an SRNE Solar hybrid inverter over Modbus.

Construct ``SrneInverter(unit)`` with a ``modbus_connection.ModbusUnit``, call
``await device.async_update()``, then read the sub-systems as plain attributes::

    device.charge_controller.battery_voltage
    device.inverter.run_mode

The register map is derived from the SRNE plugin of
`homeassistant-solax-modbus <https://github.com/wills106/homeassistant-solax-modbus>`_
(Apache-2.0). Every register is read-only there, so this library reads only.
ASCII-over-TCP framing is not supported.
"""

from .charge_controller import ChargeController
from .device import MANUFACTURER, SrneInverter
from .device_info import SERIAL_ADDRESS, SERIAL_ADDRESS_FALLBACK, DeviceInformation
from .enums import ChargerState, RunMode
from .inverter import Inverter
from .model import UpdateReport

__all__ = [
    "MANUFACTURER",
    "SERIAL_ADDRESS",
    "SERIAL_ADDRESS_FALLBACK",
    "ChargeController",
    "ChargerState",
    "DeviceInformation",
    "Inverter",
    "RunMode",
    "SrneInverter",
    "UpdateReport",
]
