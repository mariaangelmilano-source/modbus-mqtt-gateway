"""Serial-side transports. The gateway only needs `exchange(request) -> response`."""
from __future__ import annotations

from typing import Protocol

from .device_sim import SimulatedSlave


class Transport(Protocol):
    def exchange(self, frame: bytes) -> bytes | None: ...


class LoopbackTransport:
    """Routes requests to one or more simulated slaves on a virtual RS-485 bus."""

    def __init__(self, *slaves: SimulatedSlave):
        self.slaves = slaves

    def exchange(self, frame: bytes) -> bytes | None:
        for slave in self.slaves:
            answer = slave.handle(frame)
            if answer is not None:
                return answer
        return None  # timeout: nobody answered


class SerialTransport:  # pragma: no cover - needs real hardware
    """RS-485 / RS-232 transport using pyserial (optional dependency)."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 0.5):
        import serial  # type: ignore

        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def exchange(self, frame: bytes) -> bytes | None:
        self._serial.reset_input_buffer()
        self._serial.write(frame)
        header = self._serial.read(3)
        if len(header) < 3:
            return None
        if header[1] & 0x80:  # exception frame: 3 header bytes + 2 CRC
            return header + self._serial.read(2)
        return header + self._serial.read(header[2] + 2)
