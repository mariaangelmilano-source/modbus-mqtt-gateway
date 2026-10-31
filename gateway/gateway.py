"""Polls Modbus RTU devices and republishes each register as an MQTT tag."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .modbus_rtu import ModbusError, ReadRequest, decode_read_response
from .publisher import Publisher
from .transport import Transport


@dataclass(frozen=True)
class Tag:
    name: str
    register: int
    scale: float = 1.0
    unit: str = ""


@dataclass
class Device:
    name: str
    slave_id: int
    function: int
    start: int
    count: int
    tags: list[Tag] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Device":
        tags = [Tag(**t) for t in d.get("tags", [])]
        return cls(d["name"], d["slave_id"], d.get("function", 3), d["start"], d["count"], tags)


@dataclass
class Stats:
    polls: int = 0
    ok: int = 0
    timeouts: int = 0
    errors: int = 0


class Gateway:
    def __init__(self, transport: Transport, publisher: Publisher, devices: list[Device],
                 topic_prefix: str = "plant", retries: int = 2, clock=time.time):
        self.transport = transport
        self.publisher = publisher
        self.devices = devices
        self.topic_prefix = topic_prefix.rstrip("/")
        self.retries = retries
        self.clock = clock
        self.stats = Stats()

    def _read(self, device: Device) -> list[int] | None:
        request = ReadRequest(device.slave_id, device.function, device.start, device.count)
        frame = request.encode()
        for _ in range(self.retries + 1):
            self.stats.polls += 1
            answer = self.transport.exchange(frame)
            if answer is None:
                self.stats.timeouts += 1
                continue
            try:
                values = decode_read_response(answer, request)
            except ModbusError:
                self.stats.errors += 1
                continue
            self.stats.ok += 1
            return values
        return None

    def poll_once(self) -> None:
        for device in self.devices:
            values = self._read(device)
            ts = self.clock()
            base = f"{self.topic_prefix}/{device.name}"
            if values is None:
                self.publisher.publish(f"{base}/status", {"ts": ts, "online": False}, qos=1, retain=True)
                continue
            self.publisher.publish(f"{base}/status", {"ts": ts, "online": True}, qos=1, retain=True)
            for tag in device.tags:
                raw = values[tag.register - device.start]
                self.publisher.publish(
                    f"{base}/{tag.name}",
                    {"ts": ts, "value": round(raw * tag.scale, 4), "raw": raw, "unit": tag.unit},
                )

    def run(self, interval: float = 1.0, cycles: int | None = None, on_cycle=None) -> None:
        n = 0
        while cycles is None or n < cycles:
            self.poll_once()
            if on_cycle:
                on_cycle()
            n += 1
            if cycles is None or n < cycles:
                time.sleep(interval)
