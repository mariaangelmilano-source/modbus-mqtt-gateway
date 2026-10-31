import pytest

from gateway.device_sim import SimulatedSlave
from gateway.gateway import Device, Gateway, Tag
from gateway.modbus_rtu import (
    CRCError,
    ModbusExceptionResponse,
    ReadRequest,
    check_crc,
    crc16,
    decode_read_response,
    encode_exception,
    encode_read_response,
)
from gateway.publisher import MemoryPublisher
from gateway.transport import LoopbackTransport


def test_crc_known_vector():
    # Classic example from the Modbus spec: read 2 holding registers from slave 1 at 0x0000
    assert ReadRequest(1, 3, 0, 2).encode().hex() == "010300000002c40b"
    assert crc16(bytes.fromhex("010300000002")) == 0x0BC4


def test_request_roundtrip_and_validation():
    req = ReadRequest(17, 4, 10, 3)
    assert ReadRequest.decode(req.encode()) == req
    with pytest.raises(ValueError):
        ReadRequest(0, 3, 0, 1).encode()
    with pytest.raises(ValueError):
        ReadRequest(1, 6, 0, 1).encode()
    with pytest.raises(ValueError):
        ReadRequest(1, 3, 0, 200).encode()


def test_response_decoding():
    req = ReadRequest(1, 3, 0, 3)
    frame = encode_read_response(1, 3, [1, 256, 65535])
    assert decode_read_response(frame, req) == [1, 256, 65535]


def test_bad_crc_is_rejected():
    frame = bytearray(encode_read_response(1, 3, [42]))
    frame[-1] ^= 0xFF
    with pytest.raises(CRCError):
        check_crc(bytes(frame))


def test_exception_response():
    req = ReadRequest(1, 3, 100, 1)
    with pytest.raises(ModbusExceptionResponse) as exc:
        decode_read_response(encode_exception(1, 3, 0x02), req)
    assert exc.value.code == 0x02


def test_simulator_answers_only_its_id_and_flags_bad_address():
    sim = SimulatedSlave(slave_id=5, size=8)
    assert sim.handle(ReadRequest(1, 3, 0, 1).encode()) is None
    with pytest.raises(ModbusExceptionResponse):
        decode_read_response(sim.handle(ReadRequest(5, 3, 6, 4).encode()), ReadRequest(5, 3, 6, 4))


def _gateway(sim, retries=2):
    device = Device("boiler", sim.slave_id, 3, 0, 3,
                    [Tag("temperature", 0, 0.1, "degC"), Tag("flow", 2, 1, "l/min")])
    pub = MemoryPublisher()
    gw = Gateway(LoopbackTransport(sim), pub, [device], topic_prefix="plant", retries=retries, clock=lambda: 1.0)
    return gw, pub


def test_gateway_publishes_scaled_tags():
    sim = SimulatedSlave(slave_id=1)
    gw, pub = _gateway(sim)
    gw.poll_once()
    topics = {t: p for t, p, *_ in pub.messages}
    assert topics["plant/boiler/status"]["online"] is True
    temp = topics["plant/boiler/temperature"]
    assert temp["value"] == round(sim.registers[0] * 0.1, 4)
    assert temp["unit"] == "degC"
    assert gw.stats.ok == 1


def test_gateway_marks_device_offline_on_timeout():
    sim = SimulatedSlave(slave_id=9)  # gateway polls slave 1, nobody answers
    device = Device("ghost", 1, 3, 0, 1, [Tag("x", 0)])
    pub = MemoryPublisher()
    gw = Gateway(LoopbackTransport(sim), pub, [device], retries=1, clock=lambda: 1.0)
    gw.poll_once()
    assert pub.messages == [("plant/ghost/status", {"ts": 1.0, "online": False}, 1, True)]
    assert gw.stats.timeouts == 2


def test_gateway_retries_after_crc_errors():
    sim = SimulatedSlave(slave_id=1, corrupt_rate=0.5, seed=3)
    gw, pub = _gateway(sim, retries=5)
    for _ in range(20):
        gw.poll_once()
        sim.step()
    assert gw.stats.errors > 0
    assert gw.stats.ok == 20  # every cycle eventually succeeded
