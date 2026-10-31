"""Northbound publishers. MQTT is optional so the core runs with the standard library only."""
from __future__ import annotations

import json
from typing import Protocol


class Publisher(Protocol):
    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False) -> None: ...


class MemoryPublisher:
    """Keeps every message in a list. Used by tests and dry runs."""

    def __init__(self):
        self.messages: list[tuple[str, dict, int, bool]] = []

    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False) -> None:
        self.messages.append((topic, payload, qos, retain))


class StdoutPublisher:
    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False) -> None:
        print(f"{topic} {json.dumps(payload, ensure_ascii=False)}")


class PahoPublisher:  # pragma: no cover - needs a broker
    """Publishes to an MQTT broker with paho-mqtt (pip install paho-mqtt)."""

    def __init__(self, host: str = "localhost", port: int = 1883, client_id: str = "modbus-gateway"):
        import paho.mqtt.client as mqtt  # type: ignore

        self._client = mqtt.Client(client_id=client_id)
        self._client.connect(host, port)
        self._client.loop_start()

    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False) -> None:
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
