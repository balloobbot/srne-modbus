# srne-modbus

A standalone Python library that reads an **SRNE Solar** hybrid inverter /
charge controller over Modbus, exposed as a normal, object-oriented Python API.

The register map is based on the SRNE plugin of
[homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus)
(Apache-2.0), and is verified in tests against an in-memory mock of the device.

## Design

- It **consumes the connection abstraction**, not a backend: the API takes a
  [`modbus_connection.ModbusUnit`](https://github.com/home-assistant-libs/modbus-connection)
  and reads through it. You choose and own the connection.
- An `SrneInverter` is a small tree of independently-updatable sub-systems, each
  a `Component` that knows its own registers:

  | Attribute | What |
  | --- | --- |
  | `serial_number` | the inverter serial, read once at setup |
  | `charge_controller` | battery state of charge, voltage, current and power; the two PV inputs; charger state |
  | `inverter` | grid and inverter AC voltage/current/frequency, load current, mains and PV battery-charge currents, the three temperatures |

- **Setup once, then poll.** The serial number cannot change while the inverter
  runs, so it is read by `async_setup()` (which `async_update()` runs for you on
  the first call). Each later poll is two block reads.
- Everything lives in the holding-register space (FC03). This device exposes no
  coils, no input registers and no 32-bit values.
- **The whole map is read-only.** The upstream plugin declares no numbers,
  selects, switches or buttons for SRNE, so no register here is writable and
  `write()` raises for every field. This library does not invent write support.

## Supported device variants

**One.** The upstream plugin carries the shared `allowedtypes` bitmask machinery
(GEN/GEN2/GEN3/GEN4, X1/X3, PV/AC/HYBRID/MIC, EPS, DCB, PM), but every SRNE
sensor is declared `ALLDEFAULT` — an empty mask, which matches every inverter —
and its type detection only ever yields `GEN` or `HYBRID | GEN`. No register in
the SRNE map is generation- or variant-specific, so there is nothing to filter
and no per-variant components are needed. If SRNE support later grows
variant-specific registers, they belong in their own `Component` rather than in
a filter over these.

## Use

```python
import asyncio
from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from srne_modbus import SrneInverter


async def main() -> None:
    # RTU over a transparent TCP gateway. ASCII framing is NOT supported.
    conn = ModbusConnection(ModbusTcpParams(host="192.168.1.50", framer="rtu"))
    try:
        device = SrneInverter(conn.for_unit(1))
        await device.async_update()

        print("Serial:", device.serial_number)
        print("Battery:", device.charge_controller.battery_voltage, "V")
        print("State of charge:", device.charge_controller.battery_capacity_charge, "%")
        print("Charger:", device.charge_controller.charger_state)
        print("PV 1:", device.charge_controller.pv_power_1, "W")
        print("Run mode:", device.inverter.run_mode)
        print("Grid:", device.inverter.grid_voltage_meter_l1, "V")
    finally:
        await conn.close()


asyncio.run(main())
```

A poll reads each sub-system independently, the way the upstream integration
reads its blocks: one slow or refused block does not take the rest of the poll
with it. `async_update()` returns an `UpdateReport` — a failed component keeps
its previous values, does not notify its listeners, and is listed by attribute
name with its error, while every other component refreshes and notifies once
the whole poll is done. Only a dead link (`ModbusConnectionError`) raises:

```python
report = await device.async_update()
for name, error in report.failed.items():
    print(f"{name} kept its previous values: {error}")
```

A sub-system can also be refreshed on its own:

```python
await device.charge_controller.async_update()
unsub = device.charge_controller.add_update_listener(refresh_my_entity)
```

## ASCII framing is not supported

**ASCII-over-TCP is not supported under any circumstance.** This library never
constructs a connection: it takes a `ModbusUnit` you built, so the framing is
your choice — and `framer="ascii"` is not a supported configuration here. Use
`rtu` (a transparent serial gateway, which is how these inverters are normally
reached over a network) or `socket`. No connect helper in this package accepts
or forwards an ASCII framer.

## Register notes

- The serial number is a 20-register ASCII block. Upstream looks for it at
  `0x35` first and falls back to `0x300`; a serial read from the fallback block
  that does not begin with `M` or `X` is byte-swapped. Both behaviours are kept.
- Upstream defaults every SRNE sensor to an *unsigned* 16-bit read; only the
  battery current (`0x102`) and battery power (`0x10E`) are signed. That split
  is preserved exactly, because `modbus_connection.model` defaults the other way.
- Charger state has no code `3` in the upstream map. An unmapped code decodes to
  `None` here (upstream renders it as the string `"Unknown"`).
- `translator_temperature` keeps the upstream key's spelling of the transformer
  temperature, so field keys stay stable for consumers migrating from the
  integration.

## Develop / test

```bash
uv sync
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy
```

The suite runs against the in-memory mock backend that ships with
`modbus-connection` (its auto-registered `mock_modbus_unit` pytest fixture) — no
real Modbus server, backend or hardware is needed.

## License

Apache-2.0, carried over from
[homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus),
from which the register knowledge here is derived.
