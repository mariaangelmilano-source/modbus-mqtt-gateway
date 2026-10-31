# Modbus RTU → MQTT Gateway

A lightweight gateway that polls industrial devices over **Modbus RTU** (RS-485) and republishes each register as a JSON **MQTT** tag, so sensor data from legacy field equipment can reach IoT platforms, dashboards and data pipelines.

> This project is based on my undergraduate thesis (*Trabajo Especial de Grado*, B.Sc. Electrical Engineering — Electronics, Computing & Control, Universidad Central de Venezuela, 2022). In the thesis I designed and built the gateway as a hardware product: ESP32 firmware in C on FreeRTOS, a custom KiCad PCB, and field validation with a real RTU beyond 1200 m, plus a Node-RED dashboard and a Telegram bot. The original firmware state machines are in [`firmware/`](firmware/). This repository adds a Python re-implementation of the gateway logic with tests and a device simulator, so anyone can run it without hardware.

## Why it matters

Plants are full of meters, PLCs and sensors that only speak Modbus RTU over a serial bus. Modern systems expect MQTT/JSON over TCP/IP. The gateway sits in between:

```
 RS-485 bus                      Gateway                          IP network
┌──────────┐  Modbus RTU   ┌──────────────────────┐   MQTT    ┌──────────────┐
│ Slave 1  │◄────────────►│ poll ─► decode ─►     │──────────►│ Broker       │──► dashboards,
│ Slave 2  │  req / resp   │ CRC check ─► scale ─► │ JSON tags │ (Mosquitto…) │    historians,
└──────────┘               │ publish  (+ retries)  │           └──────────────┘    data pipelines
                           └──────────────────────┘
```

## Features

- Modbus RTU framing written from scratch: CRC-16 (poly 0xA001), function codes **0x03** (holding registers) and **0x04** (input registers), exception responses.
- Config-driven register map: each tag has a register, scale factor and unit (`config.example.json`).
- Topic layout `<prefix>/<device>/<tag>` plus a retained `<prefix>/<device>/status` message (online/offline).
- Retries on timeouts and CRC errors, with poll statistics.
- Pluggable transports (simulated bus, or a real serial port via `pyserial`) and publishers (stdout, in-memory, or a real broker via `paho-mqtt`).
- Standard library only for the core; 9 unit tests; CI on GitHub Actions.

## Quick start

```bash
git clone https://github.com/mariaangelmilano-source/modbus-mqtt-gateway.git
cd modbus-mqtt-gateway
python -m gateway --config config.example.json --cycles 5
```

Sample output:

```
plant/line1/boiler/status {"ts": 1793408115.70, "online": true}
plant/line1/boiler/temperature {"ts": 1793408115.70, "value": 23.5, "raw": 235, "unit": "degC"}
plant/line1/boiler/pressure {"ts": 1793408115.70, "value": 101.7, "raw": 10170, "unit": "kPa"}
```

With real hardware and a broker:

```bash
pip install pyserial paho-mqtt
python -m gateway --serial-port /dev/ttyUSB0 --mqtt-host localhost --cycles 0
```

## Tests

```bash
pip install pytest
pytest -q
```

The tests cover the CRC against the Modbus specification vector, request/response encoding, exception frames, the simulator, tag scaling, offline detection and recovery from corrupted frames.

## Project layout

```
gateway/
  modbus_rtu.py   # framing, CRC, encode/decode
  device_sim.py   # simulated slave with a realistic register map
  transport.py    # loopback (simulated bus) and serial transports
  publisher.py    # stdout, memory and MQTT publishers
  gateway.py      # polling loop, scaling, topics, retries, stats
tests/
```

## What I'd add next

- Modbus TCP and write functions (0x06/0x10) for setpoints.
- Report-by-exception (publish only on change or deadband) to cut network traffic.
- TLS and authentication for the broker connection, plus a Docker image with Mosquitto.

## Author

**María Ángel Milano** — Electrical Engineer (UCV) · M.Sc. Business Intelligence (UNIR) · [LinkedIn](https://linkedin.com/in/maria-angel-milano)
