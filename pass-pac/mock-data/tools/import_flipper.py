#!/usr/bin/env python3
"""Convert Flipper Zero .nfc/.rfid files into PASS-PAC simulator cards."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HEX_CHARS = set("0123456789abcdefABCDEF")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Flipper .nfc/.rfid files into PASS-PAC card JSON."
    )
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Path to a local UberGuidoZ/Flipper clone or exported subset.",
    )
    parser.add_argument(
        "--output",
        default=Path("mock-data/flipper-imported-cards.json"),
        type=Path,
        help="Output JSON path. Defaults to mock-data/flipper-imported-cards.json.",
    )
    parser.add_argument(
        "--merge-existing",
        type=Path,
        help="Optional existing PASS-PAC JSON file to prepend before imported cards.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of imported cards.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    imported_cards = import_flipper_cards(args.source, args.limit)
    existing_cards = load_existing_cards(args.merge_existing)
    cards = deduplicate_cards(existing_cards + imported_cards)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(cards, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Imported {len(imported_cards)} Flipper cards.")
    print(f"Wrote {len(cards)} total cards to {args.output}.")


def import_flipper_cards(source_dir: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not source_dir.exists():
        raise SystemExit(f"Source path does not exist: {source_dir}")

    cards: list[dict[str, Any]] = []
    for file_path in sorted(source_dir.rglob("*")):
        if file_path.suffix.lower() not in {".nfc", ".rfid"}:
            continue

        card = parse_flipper_file(file_path, source_dir)
        if card is None:
            continue

        cards.append(card)
        if limit is not None and len(cards) >= limit:
            break

    return cards


def parse_flipper_file(file_path: Path, source_dir: Path) -> dict[str, Any] | None:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    parsed = parse_key_value_text(text)

    if file_path.suffix.lower() == ".nfc":
        return normalize_nfc_file(file_path, source_dir, parsed)
    if file_path.suffix.lower() == ".rfid":
        return normalize_rfid_file(file_path, source_dir, parsed)
    return None


def parse_key_value_text(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    memory: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key.lower().startswith(("block ", "page ")):
            memory[key] = value
        else:
            fields[key] = value

    if memory:
        fields["memory"] = memory

    return fields


def normalize_nfc_file(
    file_path: Path,
    source_dir: Path,
    fields: dict[str, Any],
) -> dict[str, Any] | None:
    device_type = first_present(fields, "Device type", "Device Type", "Type")
    mifare_type = first_present(fields, "Mifare Classic type", "MIFARE Classic type")
    uid = normalize_uid(
        first_present(fields, "UID", "Uid") or derive_uid_from_memory(fields)
    )

    if not uid:
        return None

    card_type = derive_nfc_card_type(device_type, mifare_type, file_path)
    raw_output = {
        "device_type": device_type,
        "mifare_classic_type": mifare_type,
        "atqa": first_present(fields, "ATQA"),
        "sak": first_present(fields, "SAK"),
        "memory": fields.get("memory", {}),
    }
    raw_output = compact_dict(raw_output)

    return {
        "source": "flipper-import",
        "technology": "HF/NFC",
        "frequency": "13.56MHz",
        "card_type": card_type,
        "protocol": derive_nfc_protocol(fields),
        "uid": uid,
        "risk_level": derive_risk_level(card_type),
        "raw_output": raw_output,
        "metadata": build_metadata(file_path, source_dir, "nfc"),
        "flipper": build_nfc_flipper_profile(fields, uid, device_type, mifare_type),
    }


def normalize_rfid_file(
    file_path: Path,
    source_dir: Path,
    fields: dict[str, Any],
) -> dict[str, Any] | None:
    key_type = first_present(fields, "Key type", "Key Type", "Type")
    data = first_present(fields, "Data", "Key", "UID", "Uid")
    uid = normalize_uid(data)

    if not uid:
        return None

    card_type = key_type or file_path.stem.replace("_", " ")
    raw_output = {
        "key_type": key_type,
        "data": data,
        "bit_length": first_present(fields, "Bit length", "Bit Length"),
    }
    raw_output = compact_dict(raw_output)

    return {
        "source": "flipper-import",
        "technology": "LF RFID",
        "frequency": "125kHz",
        "card_type": card_type,
        "protocol": key_type or "Legacy RFID",
        "uid": uid,
        "risk_level": derive_risk_level(card_type),
        "raw_output": raw_output,
        "metadata": build_metadata(file_path, source_dir, "rfid"),
        "flipper": build_rfid_flipper_profile(fields, uid, key_type, data),
    }


def first_present(fields: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = fields.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def normalize_uid(value: str | None) -> str | None:
    if not value:
        return None

    hex_chars = [char for char in value if char in HEX_CHARS]
    if len(hex_chars) < 2:
        return None

    if len(hex_chars) % 2 == 1:
        hex_chars = hex_chars[:-1]

    pairs = [
        "".join(hex_chars[index : index + 2]).upper()
        for index in range(0, len(hex_chars), 2)
    ]
    return ":".join(pairs)


def derive_uid_from_memory(fields: dict[str, Any]) -> str | None:
    memory = fields.get("memory")
    if not isinstance(memory, dict):
        return None

    page_zero = memory.get("Page 0")
    page_one = memory.get("Page 1")
    block_zero = memory.get("Block 0")

    if page_zero and page_one:
        return f"{page_zero} {page_one}"
    if block_zero:
        return block_zero
    return None


def derive_nfc_card_type(
    device_type: str | None,
    mifare_type: str | None,
    file_path: Path,
) -> str:
    base_type = device_type or file_path.stem.replace("_", " ")
    if device_type and "mifare classic" in device_type.lower() and mifare_type:
        return f"MIFARE Classic {mifare_type}".strip()
    return base_type


def derive_nfc_protocol(fields: dict[str, Any]) -> str:
    if first_present(fields, "ATQA") or first_present(fields, "SAK"):
        return "ISO14443A"
    return "NFC"


def build_nfc_flipper_profile(
    fields: dict[str, Any],
    uid: str,
    device_type: str | None,
    mifare_type: str | None,
) -> dict[str, Any]:
    memory = fields.get("memory")
    memory_entries = memory if isinstance(memory, dict) else {}
    return compact_dict(
        {
            "file_type": "nfc",
            "filetype": first_present(fields, "Filetype"),
            "version": parse_int(first_present(fields, "Version")),
            "device_type": device_type,
            "mifare_classic_type": mifare_type,
            "uid_length_bytes": uid_byte_count(uid),
            "atqa": first_present(fields, "ATQA"),
            "sak": first_present(fields, "SAK"),
            "memory": summarize_memory(memory_entries),
        }
    )


def build_rfid_flipper_profile(
    fields: dict[str, Any],
    uid: str,
    key_type: str | None,
    data: str | None,
) -> dict[str, Any]:
    return compact_dict(
        {
            "file_type": "rfid",
            "filetype": first_present(fields, "Filetype"),
            "version": parse_int(first_present(fields, "Version")),
            "key_type": key_type,
            "uid_length_bytes": uid_byte_count(uid),
            "bit_length": parse_int(first_present(fields, "Bit length", "Bit Length")),
            "data_length_bytes": hex_byte_count(data or ""),
        }
    )


def summarize_memory(memory: dict[str, str]) -> dict[str, Any]:
    block_count = sum(1 for key in memory if key.lower().startswith("block "))
    page_count = sum(1 for key in memory if key.lower().startswith("page "))
    estimated_bytes = sum(hex_byte_count(value) for value in memory.values())
    return compact_dict(
        {
            "has_dump": bool(memory),
            "entry_count": len(memory),
            "block_count": block_count,
            "page_count": page_count,
            "estimated_bytes": estimated_bytes,
        }
    )


def derive_risk_level(card_type: str) -> str:
    normalized = card_type.lower()
    if any(keyword in normalized for keyword in ["mifare classic", "t5577", "hid prox"]):
        return "medium"
    if any(keyword in normalized for keyword in ["ntag", "ultralight"]):
        return "low"
    return "informational"


def build_metadata(file_path: Path, source_dir: Path, file_type: str) -> dict[str, str]:
    relative_path = file_path.relative_to(source_dir).as_posix()
    return {
        "dataset": "uberguidoz-flipper",
        "file_type": file_type,
        "source_path": relative_path,
        "source_file": file_path.name,
        "source_sha256": hashlib.sha256(
            file_path.read_bytes()
        ).hexdigest(),
    }


def uid_byte_count(uid: str) -> int:
    return len([part for part in uid.split(":") if part])


def hex_byte_count(value: str) -> int:
    hex_chars = [char for char in value if char in HEX_CHARS]
    return len(hex_chars) // 2


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "", {})}


def load_existing_cards(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []

    with path.open(encoding="utf-8") as file:
        cards = json.load(file)

    if not isinstance(cards, list):
        raise SystemExit(f"Existing card file must contain a JSON array: {path}")

    return cards


def deduplicate_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique_cards: list[dict[str, Any]] = []

    for card in cards:
        identity = (
            str(card.get("source", "")),
            str(card.get("uid", "")),
            str(card.get("metadata", {}).get("source_sha256", "")),
        )
        if identity in seen:
            continue

        seen.add(identity)
        unique_cards.append(card)

    return unique_cards


if __name__ == "__main__":
    main()
