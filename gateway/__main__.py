"""CLI: python -m gateway --config config.example.json --cycles 5"""
from __future__ import annotations

import argparse
import json

from .device_sim import SimulatedSlave
from .gateway import Device, Gateway
from .publisher import StdoutPublisher
from .transport import LoopbackTransport


def main() -> None:
    parser = argparse.ArgumentParser(description="Modbus RTU to MQTT gateway")
    parser.add_argument("--config", default="config.example.json")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--mqtt-host", help="publish to a real broker (needs paho-mqtt)")
    parser.add_argument("--serial-port", help="poll real devices on this port (needs pyserial)")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    devices = [Device.from_dict(d) for d in cfg["devices"]]

    if args.serial_port:
        from .transport import SerialTransport
        transport = SerialTransport(args.serial_port, cfg.get("baudrate", 9600))
        sims = []
    else:
        sims = [SimulatedSlave(slave_id=d.slave_id, seed=d.slave_id) for d in devices]
        transport = LoopbackTransport(*sims)

    if args.mqtt_host:
        from .publisher import PahoPublisher
        publisher = PahoPublisher(args.mqtt_host)
    else:
        publisher = StdoutPublisher()

    gw = Gateway(transport, publisher, devices, topic_prefix=cfg.get("topic_prefix", "plant"))
    gw.run(interval=args.interval, cycles=args.cycles, on_cycle=lambda: [s.step() for s in sims])
    print(f"# stats: {gw.stats}")


if __name__ == "__main__":
    main()
