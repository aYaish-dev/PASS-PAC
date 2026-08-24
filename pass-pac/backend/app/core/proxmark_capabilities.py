from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).with_name("proxmark_capabilities.json")


@lru_cache(maxsize=1)
def get_capability_registry() -> dict[str, Any]:
    with REGISTRY_PATH.open("r", encoding="utf-8") as stream:
        registry = json.load(stream)
    _validate_registry(registry)
    commands_by_key = {
        item["key"]: item for item in registry["commands"]
    }
    recipes = []
    for item in registry["recipes"]:
        recipe = dict(item)
        recipe["commands"] = [
            commands_by_key[key]["command"] for key in recipe["command_keys"]
        ]
        recipes.append(recipe)
    return {**registry, "recipes": recipes}


def command_capabilities() -> list[dict[str, Any]]:
    return list(get_capability_registry()["commands"])


def recipe_capabilities() -> list[dict[str, Any]]:
    return list(get_capability_registry()["recipes"])


def registered_commands() -> list[str]:
    return [item["command"] for item in command_capabilities()]


def command_selector_map(operation: str) -> dict[str, str]:
    return {
        item["selector"]: item["command"]
        for item in command_capabilities()
        if item["operation"] == operation
    }


def commands_for_operation(operation: str) -> list[str]:
    return [
        item["command"]
        for item in command_capabilities()
        if item["operation"] == operation
    ]


def normalize_registered_command(command: str) -> str | None:
    normalized = " ".join(command.strip().lower().split())
    # Current Proxmark3 clients expose EMV as a top-level command. Canonicalize
    # legacy operator input before allowlist validation so it is never sent as
    # the obsolete `hf emv ...` form.
    if normalized.startswith("hf emv "):
        normalized = normalized.removeprefix("hf ")
    return normalized if normalized in registered_commands() else None


def public_capability_registry() -> dict[str, Any]:
    registry = get_capability_registry()
    return {
        "version": registry["version"],
        "scope": registry["scope"],
        "commands": registry["commands"],
        "recipes": registry["recipes"],
    }


def _validate_registry(registry: dict[str, Any]) -> None:
    if not isinstance(registry.get("version"), str):
        raise RuntimeError("The Proxmark capability registry has no version.")
    commands = registry.get("commands")
    recipes = registry.get("recipes")
    if not isinstance(commands, list) or not isinstance(recipes, list):
        raise RuntimeError("The Proxmark capability registry is malformed.")

    command_keys: set[str] = set()
    command_texts: set[str] = set()
    for command in commands:
        if not isinstance(command, dict):
            raise RuntimeError("A command capability is malformed.")
        key = command.get("key")
        text = command.get("command")
        if not isinstance(key, str) or not isinstance(text, str):
            raise RuntimeError("A command capability is missing its key or command.")
        if key in command_keys or text in command_texts:
            raise RuntimeError("The Proxmark capability registry contains a duplicate command.")
        if command.get("read_only") is not True or command.get("changes_state") is not False:
            raise RuntimeError("Phase A accepts only read-only, non-state-changing commands.")
        command_keys.add(key)
        command_texts.add(text)

    recipe_keys: set[str] = set()
    for recipe in recipes:
        if not isinstance(recipe, dict) or not isinstance(recipe.get("key"), str):
            raise RuntimeError("A recipe capability is malformed.")
        if recipe["key"] in recipe_keys:
            raise RuntimeError("The Proxmark capability registry contains a duplicate recipe.")
        recipe_keys.add(recipe["key"])
        for command_key in recipe.get("command_keys", []):
            if command_key not in command_keys:
                raise RuntimeError(
                    f"Recipe '{recipe['key']}' references unknown command '{command_key}'."
                )
