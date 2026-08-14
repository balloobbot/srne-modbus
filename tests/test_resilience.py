"""One failing block must not take the rest of the poll with it.

The upstream integration reads its blocks independently and tolerates a failure
(``auto_block_ignore_readerror=True``): the failing block's sensors keep their
last values while everything else refreshes. The library mirrors that at
component granularity — here one component per upstream block.
"""

from __future__ import annotations

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit

from srne_modbus import SrneInverter

from .conftest import HOLDING


async def test_a_failed_component_leaves_the_rest_fresh(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await srne.async_update()
    before = srne.inverter.dc_dc_temperature

    mock_modbus_unit.holding[0x101] = 480  # battery voltage changes on the device
    mock_modbus_unit.holding[0x220] = 500  # so does the DC-DC temperature
    # The charge controller is read first, so it has answered by the time the
    # inverter times out — a contained timeout, not a silent device.
    mock_modbus_unit.fail_read(0x210, ModbusTimeoutError("slow inverter block"))
    report = await srne.async_update()

    assert not report.complete
    assert set(report.failed) == {"inverter"}
    assert isinstance(report.failed["inverter"], ModbusTimeoutError)
    assert report.updated == {"charge_controller"}
    assert srne.inverter.dc_dc_temperature == before
    assert srne.charge_controller.battery_voltage == pytest.approx(48.0)


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


async def test_a_silent_device_raises_on_the_first_timeout(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """Nothing answered at all, so the poll stops rather than paying N timeouts."""
    await srne.async_update()
    mock_modbus_unit.fail_requests(ModbusTimeoutError("asleep"))
    mock_modbus_unit.read_events.clear()

    with pytest.raises(ModbusTimeoutError):
        await srne.async_update()

    assert len(mock_modbus_unit.read_events) == 1  # the inverter was never tried


async def test_every_component_refreshes_on_a_healthy_device(
    srne: SrneInverter,
) -> None:
    report = await srne.async_update()
    assert report.complete
    assert report.failed == {}
    assert report.updated == {"charge_controller", "inverter"}


async def test_a_transient_serial_failure_retries_instead_of_latching_none(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A timed-out serial read must not settle the serial at ``None`` forever."""
    mock_modbus_unit.holding.update(HOLDING)
    mock_modbus_unit.fail_read(0x35, ModbusTimeoutError("busy"))
    device = SrneInverter(mock_modbus_unit)

    with pytest.raises(ModbusTimeoutError):
        await device.async_update()
    assert device.serial_number is None

    mock_modbus_unit.fail_read(0x35, None)
    report = await device.async_update()
    assert device.serial_number == "MSRNE12345"
    assert report.complete


async def test_a_dead_link_at_setup_raises(mock_modbus_unit: MockModbusUnit) -> None:
    mock_modbus_unit.holding.update(HOLDING)
    mock_modbus_unit.fail_requests(ModbusConnectionError("link down"))
    device = SrneInverter(mock_modbus_unit)
    with pytest.raises(ModbusConnectionError):
        await device.async_update()


async def test_a_transient_failure_on_the_fallback_block_also_retries(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """An absent primary block is permanent; a fallback that times out is not."""
    mock_modbus_unit.holding.update(HOLDING)
    mock_modbus_unit.fail_read(0x35, IllegalDataAddressError())
    mock_modbus_unit.fail_read(0x300, ModbusTimeoutError("busy"))
    device = SrneInverter(mock_modbus_unit)
    with pytest.raises(ModbusTimeoutError):
        await device.async_update()
