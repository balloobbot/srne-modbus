"""Decoding, identity and read-plan tests over the in-memory mock backend."""

from __future__ import annotations

import pytest
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit

from srne_modbus import ChargerState, RunMode, SrneInverter

from .conftest import HOLDING, SERIAL, ascii_registers


async def test_charge_controller(srne: SrneInverter) -> None:
    await srne.async_update()
    cc = srne.charge_controller
    assert cc.battery_capacity_charge == 87
    assert cc.battery_voltage == pytest.approx(53.2)
    assert cc.battery_current == pytest.approx(-5.0)  # signed
    assert cc.pv_voltage_1 == pytest.approx(321.0)
    assert cc.pv_current_1 == pytest.approx(4.5)
    assert cc.pv_power_1 == 1445
    assert cc.charger_state is ChargerState.CONSTANT_VOLTAGE_CHARGE
    assert cc.battery_power == -1000  # signed
    assert cc.pv_voltage_2 == pytest.approx(298.0)
    assert cc.pv_current_2 == pytest.approx(3.3)
    assert cc.pv_power_2 == 983


async def test_inverter(srne: SrneInverter) -> None:
    await srne.async_update()
    inv = srne.inverter
    assert inv.run_mode is RunMode.INVERTER_POWERED_OPERATION
    assert inv.grid_voltage_meter_l1 == pytest.approx(230.1)
    assert inv.grid_current_l1 == pytest.approx(2.7)
    assert inv.grid_frequency_l1 == pytest.approx(49.98)
    assert inv.inverter_voltage_meter_l1 == pytest.approx(229.9)
    assert inv.inverter_current_l1 == pytest.approx(4.1)
    assert inv.inverter_frequency_l1 == pytest.approx(50.01)
    assert inv.load_current_l1 == pytest.approx(3.8)
    assert inv.battery_charge_mains == pytest.approx(12.0)
    assert inv.dc_dc_temperature == pytest.approx(41.5)
    assert inv.dc_ac_temperature == pytest.approx(38.8)
    assert inv.translator_temperature == pytest.approx(50.2)
    assert inv.battery_charge_pv == pytest.approx(21.0)


async def test_unsigned_fields_do_not_wrap_negative(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Upstream defaults registers to unsigned; a high word must stay positive."""
    mock_modbus_unit.holding[0x101] = 0xFFCE  # 65486 raw
    device = SrneInverter(mock_modbus_unit)
    await device.charge_controller.async_update()
    assert device.charge_controller.battery_voltage == pytest.approx(6548.6)


async def test_unmapped_enum_code_is_none(mock_modbus_unit: MockModbusUnit) -> None:
    """Charger-state code 3 has no meaning upstream, so it decodes to None."""
    mock_modbus_unit.holding[0x10B] = 3
    device = SrneInverter(mock_modbus_unit)
    await device.charge_controller.async_update()
    assert device.charge_controller.charger_state is None


async def test_serial_number(srne: SrneInverter) -> None:
    await srne.async_update()
    assert srne.serial_number == SERIAL
    assert srne.manufacturer == "SRNE Solar"


async def test_serial_number_falls_back_and_swaps(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A fallback-block serial not starting with M or X is byte-swapped."""
    mock_modbus_unit.holding.update(HOLDING)
    del mock_modbus_unit.holding[0x35]
    mock_modbus_unit.holding[0x300] = ascii_registers("RSEN2143")
    device = SrneInverter(mock_modbus_unit)
    await device.async_update()
    assert device.serial_number == "SRNE1234"


async def test_serial_number_fallback_not_swapped_when_recognised(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    mock_modbus_unit.holding.update(HOLDING)
    del mock_modbus_unit.holding[0x35]
    mock_modbus_unit.holding[0x300] = ascii_registers("MSRNE1234")
    device = SrneInverter(mock_modbus_unit)
    await device.async_update()
    assert device.serial_number == "MSRNE1234"


async def test_serial_number_absent_does_not_fail_the_poll(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device refusing both serial blocks still polls its measurements."""
    mock_modbus_unit.holding.update(HOLDING)
    mock_modbus_unit.fail_read(0x35, IllegalDataAddressError())
    mock_modbus_unit.fail_read(0x300, IllegalDataAddressError())
    device = SrneInverter(mock_modbus_unit)
    await device.async_update()
    assert device.serial_number is None
    assert device.charge_controller.battery_voltage == pytest.approx(53.2)


async def test_setup_runs_once(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """The serial block is read at setup and never again."""
    await srne.async_update()
    await srne.async_update()
    serial_reads = [e for e in mock_modbus_unit.read_events if e.address == 0x35]
    assert len(serial_reads) == 1


async def test_poll_read_plan(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """A poll costs two holding-register reads, one per contiguous device block.

    The upstream plugin's auto-blocker produces the same two blocks, since its
    100-register block size splits between 0x111 and 0x210.
    """
    await srne.async_setup()
    mock_modbus_unit.read_events.clear()
    await srne.async_update()

    blocks = [
        (e.register_type, e.address, e.count) for e in mock_modbus_unit.read_events
    ]
    assert blocks == [
        ("holding", 0x100, 0x111 - 0x100 + 1),
        ("holding", 0x210, 0x224 - 0x210 + 1),
    ]
    assert all(count <= 100 for _, _, count in blocks)


async def test_read_plan_covers_every_field(srne: SrneInverter) -> None:
    """Every declared register falls inside a block the poll reads."""
    addresses: set[int] = set()
    for component in (srne.charge_controller, srne.inverter):
        addresses |= set((await component.async_read_raw())["holding"])
    declared = {
        field.address
        for component in (srne.charge_controller, srne.inverter)
        for field in component.declared_fields.values()
    }
    assert declared <= addresses


async def test_serial_block_read_plan(
    srne: SrneInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await srne.async_setup()
    assert [(e.address, e.count) for e in mock_modbus_unit.read_events] == [(0x35, 20)]


async def test_registers_are_read_only(srne: SrneInverter) -> None:
    """SRNE declares no writable registers upstream, so nothing here is writable."""
    for component in (srne.charge_controller, srne.inverter):
        assert not any(f.writable for f in component.declared_fields.values())
    with pytest.raises(AttributeError):
        await srne.charge_controller.write("battery_voltage", 50.0)


async def test_field_count_matches_upstream(srne: SrneInverter) -> None:
    """24 sensor entities upstream, 24 fields here."""
    total = sum(
        len(component.declared_fields)
        for component in (srne.charge_controller, srne.inverter)
    )
    assert total == 24
