"""Minimal Modbus RTU framing: CRC-16, request builders and response parsers.

Only the function codes a polling gateway needs are implemented:
0x03 Read Holding Registers and 0x04 Read Input Registers.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

READ_HOLDING_REGISTERS = 0x03
READ_INPUT_REGISTERS = 0x04
SUPPORTED_FUNCTIONS = (READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS)

EXCEPTION_CODES = {
    0x01: "Illegal function",
    0x02: "Illegal data address",
    0x03: "Illegal data value",
    0x04: "Slave device failure",
}


class ModbusError(Exception):
    """Base error for framing problems."""


class CRCError(ModbusError):
    """Frame received with a bad checksum."""


class ModbusExceptionResponse(ModbusError):
    """The slave answered with an exception code."""

    def __init__(self, function: int, code: int):
        self.function = function
        self.code = code
        super().__init__(f"function 0x{function:02X}: {EXCEPTION_CODES.get(code, 'Unknown')} (0x{code:02X})")


def crc16(data: bytes) -> int:
    """Modbus CRC-16 (poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def with_crc(payload: bytes) -> bytes:
    """Append the CRC low byte first, as Modbus RTU requires."""
    return payload + struct.pack("<H", crc16(payload))


def check_crc(frame: bytes) -> bytes:
    """Validate and strip the CRC; return the payload."""
    if len(frame) < 4:
        raise ModbusError(f"frame too short ({len(frame)} bytes)")
    payload, received = frame[:-2], struct.unpack("<H", frame[-2:])[0]
    if crc16(payload) != received:
        raise CRCError(f"CRC mismatch: got 0x{received:04X}, expected 0x{crc16(payload):04X}")
    return payload


@dataclass(frozen=True)
class ReadRequest:
    slave: int
    function: int
    address: int
    count: int

    def encode(self) -> bytes:
        if not 1 <= self.slave <= 247:
            raise ValueError("slave id must be 1..247")
        if self.function not in SUPPORTED_FUNCTIONS:
            raise ValueError(f"unsupported function 0x{self.function:02X}")
        if not 1 <= self.count <= 125:
            raise ValueError("count must be 1..125 registers")
        return with_crc(struct.pack(">BBHH", self.slave, self.function, self.address, self.count))

    @classmethod
    def decode(cls, frame: bytes) -> "ReadRequest":
        payload = check_crc(frame)
        if len(payload) != 6:
            raise ModbusError("read request payload must be 6 bytes")
        slave, function, address, count = struct.unpack(">BBHH", payload)
        return cls(slave, function, address, count)


def encode_read_response(slave: int, function: int, registers: list[int]) -> bytes:
    body = b"".join(struct.pack(">H", r & 0xFFFF) for r in registers)
    return with_crc(struct.pack(">BBB", slave, function, len(body)) + body)


def encode_exception(slave: int, function: int, code: int) -> bytes:
    return with_crc(struct.pack(">BBB", slave, function | 0x80, code))


def decode_read_response(frame: bytes, request: ReadRequest) -> list[int]:
    """Parse a 0x03/0x04 response and return the register values."""
    payload = check_crc(frame)
    slave, function = payload[0], payload[1]
    if slave != request.slave:
        raise ModbusError(f"response from slave {slave}, expected {request.slave}")
    if function == request.function | 0x80:
        raise ModbusExceptionResponse(request.function, payload[2])
    if function != request.function:
        raise ModbusError(f"unexpected function 0x{function:02X}")
    byte_count = payload[2]
    data = payload[3:]
    if byte_count != len(data) or byte_count != 2 * request.count:
        raise ModbusError("byte count does not match the requested register count")
    return [v for (v,) in struct.iter_unpack(">H", data)]
