import json
from pathlib import Path
from random import SystemRandom
from typing import Any


class SimulatorAdapter:
    def __init__(self, mock_data_dir: str) -> None:
        self.mock_data_dir = Path(mock_data_dir)
        self._random = SystemRandom()

    def pick_card(
        self,
        technology: str | None = None,
        card_type: str | None = None,
    ) -> dict[str, Any]:
        cards = self._load_cards()
        filtered_cards = [
            card
            for card in cards
            if self._matches(card, "technology", technology)
            and self._matches(card, "card_type", card_type)
        ]

        if not filtered_cards:
            raise ValueError("No simulator card matched the requested filters.")

        return self._random.choice(filtered_cards)

    def _load_cards(self) -> list[dict[str, Any]]:
        file_path = self.mock_data_dir / "sample-cards.json"
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
