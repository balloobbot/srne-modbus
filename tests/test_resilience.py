"""One failing block must not take the rest of the poll with it.

The upstream integration reads its blocks independently and tolerates a failure
(``auto_block_ignore_readerror=True``): the failing block's sensors keep their
last values while everything else refreshes. The library mirrors that at
component granularity — here one component per upstream block.
"""

from __future__ import annotations

import pytest
from modbus_connection import ModbusConnectionError, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit

from srne_modbus import SrneInverter


async def test_a_failed_component_leaves_the_rest_fresh(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await srne.async_update()
    before = srne.charge_controller.battery_voltage

    mock_modbus_unit.holding[0x101] = 480  # battery voltage changes on the device
    mock_modbus_unit.holding[0x220] = 500  # so does the DC-DC temperature
    mock_modbus_unit.fail_read(0x100, ModbusTimeoutError("slow charge block"))
    report = await srne.async_update()

    assert not report.complete
    assert set(report.failed) == {"charge_controller"}
    assert isinstance(report.failed["charge_controller"], ModbusTimeoutError)
    assert report.updated == {"inverter"}
    assert srne.charge_controller.battery_voltage == before
    assert srne.inverter.dc_dc_temperature == pytest.approx(50.0)


async def test_listeners_fire_at_the_end_and_only_for_fresh_components(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await srne.async_update()
    seen: list[int] = []
    srne.charge_controller.add_update_listener(
        lambda: seen.append(len(mock_modbus_unit.read_events))
    )
    srne.inverter.add_update_listener(lambda: seen.append(-1))

    # The failure is on the second block read, so a charge-controller listener
    # that fired inline would see one read event rather than both.
    mock_modbus_unit.fail_read(0x210, ModbusTimeoutError("slow inverter block"))
    mock_modbus_unit.read_events.clear()
    await srne.async_update()

    # One notification, after every component was tried; none for the failure.
    assert len(mock_modbus_unit.read_events) == 2
    assert seen == [2]


async def test_a_dead_link_raises_instead_of_reporting(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await srne.async_update()
    mock_modbus_unit.fail_requests(ModbusConnectionError("link down"))
    with pytest.raises(ModbusConnectionError):
        await srne.async_update()


async def test_every_component_refreshes_on_a_healthy_device(
    srne: SrneInverter,
) -> None:
    report = await srne.async_update()
    assert report.complete
    assert report.failed == {}
    assert report.updated == {"charge_controller", "inverter"}
