# Original thesis firmware (ESP32 + FreeRTOS)

These two files are the state machines printed in Appendices II and III of my undergraduate thesis, *"Diseño de una puerta de enlace entre una red Modbus RTU y un servidor MQTT para transmisión y recepción de datos"* (Universidad Central de Venezuela, April 2022; academic advisor: Prof. José Alonso).

## How the hardware gateway works

Two identical devices replace the physical RS-485 link between a Modbus master and its slaves:

```
Modbus master ──RS-485──► [ESP32 gateway, master side] ──MQTT topic master→slave──►  broker
                                                                                       │
Modbus slave(s) ◄──RS-485── [ESP32 gateway, slave side] ◄──────────────────────────────┘
        (the response travels back on topic slave→master)
```

- **Hardware:** ESP32 development board, RS-485 transceiver, custom 2-layer PCB designed in KiCad 5.1.5 (IPC/IEC track widths), manufactured by JLCPCB, hand-soldered (incl. SMD) and mounted in a DIN-rail enclosure.
- **Firmware:** C on ESP-IDF / FreeRTOS (PlatformIO), modular code, one FreeRTOS task per state machine, UART queues, task watchdog, LED status codes. Arduino libraries WiFi, PubSubClient and ArduinoJson.
- **Data path:** each serial Modbus RTU frame is wrapped into JSON with a sequence counter, published over MQTT, unwrapped on the other side and written back to the RS-485 bus. The counter discards stale responses.
- **Validation:** Modbus Poll / Modbus Slave, Realterm and MQTTBox; tests across baud rates (best at 9600 baud), QoS levels, several slaves and register counts; a real temperature/humidity RTU (FTHT01) queried through the gateway, beyond 1200 m (the RS-485 cable limit).
- **Extensions:** Node-RED on a Raspberry Pi as a virtual master, a Telegram bot that logs and triggers Modbus queries, and a live temperature/humidity dashboard.

## Files

| File | Thesis appendix | Role |
|---|---|---|
| `src/state_machine_master_to_slave.cpp` | II | Device next to the master: waits for an RS-485 request, encapsulates it in JSON, subscribes/publishes, waits for the slave's answer and writes it to the bus |
| `src/state_machine_slave_to_master.cpp` | III | Device next to the slave(s): receives the request topic, writes it to RS-485, reads the slave's answer and publishes it back |

The code is transcribed from the thesis PDF, so its original formatting is kept. Helper modules (JSON conversion, WiFi/MQTT reconnection, UART drivers and queues) were not printed in the thesis and are not included.
