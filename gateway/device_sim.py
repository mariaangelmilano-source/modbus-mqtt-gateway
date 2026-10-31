"""A simulated Modbus RTU slave, so the gateway can be demoed and tested without hardware."""
from __future__ import annotations

import math
import random

from .modbus_rtu import (
    SUPPORTED_FUNCTIONS,
    ModbusError,
    ReadRequest,
    encode_exception,
    encode_read_response,
)


class SimulatedSlave:
    """Holds a register map and answers read requests like an industrial sensor would.

    Registers 0..9 are filled with a slowly varying signal (temperature x10,
    pressure x100, flow, status) so the published values look realistic.
    """

    def __init__(self, slave_id: int = 1, size: int = 64, seed: int = 7, corrupt_rate: float = 0.0):
        self.slave_id = slave_id
        self.registers = [0] * size
        self.corrupt_rate = corrupt_rate
        self._rng = random.Random(seed)
        self._tick = 0
        self.step()

    def step(self) -> None:
        """Advance the simulated process by one sample."""
        t = self._tick
        self.registers[0] = int(235 + 15 * math.sin(t / 10))          # temperature, 0.1 °C
        self.registers[1] = int(10130 + 40 * math.cos(t / 7))          # pressure, 0.01 kPa (~101.3 kPa)
        self.registers[2] = int(500 + self._rng.randint(-20, 20))      # flow, l/min
        self.registers[3] = 1 if (t // 50) % 2 == 0 else 0             # pump status
        self._tick += 1

    def handle(self, frame: bytes) -> bytes | None:
        """Return the response frame, or None when the request is not for this slave."""
        try:
            req = ReadRequest.decode(frame)
        except ModbusError:
            return None  # a real slave stays silent on a corrupted request
        if req.slave != self.slave_id:
            return None
        if req.function not in SUPPORTED_FUNCTIONS:
            return encode_exception(self.slave_id, req.function, 0x01)
        if req.address + req.count > len(self.registers):
            return encode_exception(self.slave_id, req.function, 0x02)
        response = encode_read_response(
            self.slave_id, req.function, self.registers[req.address : req.address + req.count]
        )
        if self.corrupt_rate and self._rng.random() < self.corrupt_rate:
            response = response[:-1] + bytes([response[-1] ^ 0xFF])  # flip CRC bits
        return response
