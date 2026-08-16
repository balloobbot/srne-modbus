#!/usr/bin/env python3

"""Query an SRNE inverter / charge controller and print every value.

Reads one device once and dumps it to the terminal — the quickest way to check
real hardware with no application around it.

::

    uv run script/query.py /dev/ttyUSB0 --transport serial --unit 1
    uv run script/query.py 192.168.1.50 --unit 1 --framer rtu
"""

from __future__ import annotations

import argparse
import asyncio

from modbus_connection import ModbusError
from modbus_connection.cli_helper import (
    CountingUnit,
    add_connection_args,
    connect_from_args,
    print_component,
)

from srne_modbus import SrneInverter

# The device is RS-485 RTU; over TCP it is reached through a gateway, which
# presents it either transparently (rtu) or as native Modbus TCP (socket).
# ASCII framing is not supported. tcp leads: it is the default transport.
CONNECTIONS = (("tcp", "rtu"), ("tcp", "socket"), ("serial", "rtu"))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_connection_args(parser, connections=CONNECTIONS)
    parser.add_argument("--unit", type=int, default=1, help="Modbus unit id")
    args = parser.parse_args()

    try:
        connection = await connect_from_args(args)
    except ModbusError as err:
        print(f"Could not connect: {err}")
        return 1

    counting = CountingUnit(connection.for_unit(args.unit))
    device = SrneInverter(counting)
    try:
        report = await device.async_update()
    except ModbusError as err:
        print(f"Could not read the inverter: {err}")
        return 1
    finally:
        await connection.close()

    # A failed sub-system still prints, holding its previous values — say so,
    # or its empty values read as the device's answer.
    for name, error in report.failed.items():
        print(f"{name} was not read: {error}")

    print(f"Serial number: {device.serial_number}")
    print_component(device.charge_controller, title="Charge controller")
    print_component(device.inverter, title="Inverter")
    print(f"\n{counting.reads} Modbus reads")
    return 0


raise SystemExit(asyncio.run(main()))
