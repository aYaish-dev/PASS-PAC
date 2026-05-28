import json
from pathlib import Path
from random import SystemRandom
from typing import Any


class SimulatorAdapter:
    def __init__(self, mock_data_dir: str, card_file_name: str = "sample-cards.json") -> None:
        self.mock_data_dir = Path(mock_data_dir)
        self.card_file_name = card_file_name
        self._random = SystemRandom()

    def pick_card(
        self,
        technology: str | None = None,
        card_type: str | None = None,
        source: str | None = None,
        dataset: str | None = None,
        file_type: str | None = None,
        uid: str | None = None,
    ) -> dict[str, Any]:
        cards = self._load_cards()
        filtered_cards = [
            card
            for card in cards
            if self._matches(card, "technology", technology)
            and self._matches(card, "card_type", card_type)
            and self._matches(card, "source", source)
            and self._matches_any(card, dataset, ("dataset",), ("metadata", "dataset"))
            and self._matches_any(
                card,
                file_type,
                ("file_type",),
                ("metadata", "file_type"),
                ("flipper", "file_type"),
            )
            and self._matches(card, "uid", uid)
        ]

        if not filtered_cards:
            raise ValueError("No simulator card matched the requested filters.")

        return self._random.choice(filtered_cards)

    def _load_cards(self) -> list[dict[str, Any]]:
        file_path = self.mock_data_dir / self.card_file_name
        with file_path.open(encoding="utf-8") as file:
            cards = json.load(file)

        if not isinstance(cards, list) or not cards:
            raise ValueError("Simulator card data must be a non-empty JSON array.")

        return cards

    @staticmethod
    def _matches(
        card: dict[str, Any],
        field_name: str,
        expected_value: str | None,
    ) -> bool:
        if expected_value is None:
            return True

        actual_value = str(card.get(field_name, "")).lower()
        return actual_value == expected_value.lower()

    @classmethod
    def _matches_any(
        cls,
        card: dict[str, Any],
        expected_value: str | None,
        *paths: tuple[str, ...],
    ) -> bool:
        if expected_value is None:
            return True

        normalized_expected = expected_value.lower()
        return any(
            str(value).lower() == normalized_expected
            for value in (cls._read_path(card, path) for path in paths)
            if value is not None
        )

    @staticmethod
    def _read_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
        current_value: Any = data
        for part in path:
            if not isinstance(current_value, dict):
                return None
            current_value = current_value.get(part)
        return current_value
