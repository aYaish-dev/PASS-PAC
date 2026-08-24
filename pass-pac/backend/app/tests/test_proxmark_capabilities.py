import unittest

from app.adapters.proxmark_adapter import SAFE_COMMANDS, normalize_safe_command
from app.core.proxmark_capabilities import (
    command_capabilities,
    command_selector_map,
    get_capability_registry,
    recipe_capabilities,
)


class ProxmarkCapabilityRegistryTests(unittest.TestCase):
    def test_registry_is_versioned_and_read_only(self) -> None:
        registry = get_capability_registry()

        self.assertEqual(registry["version"], "proxmark-capability-registry-v1.1")
        self.assertEqual(
            registry["scope"], "authorized-read-only-evidence-acquisition"
        )
        self.assertTrue(command_capabilities())
        self.assertTrue(
            all(item["read_only"] and not item["changes_state"] for item in command_capabilities())
        )

    def test_every_recipe_resolves_to_registered_commands(self) -> None:
        commands_by_key = {item["key"]: item["command"] for item in command_capabilities()}

        for recipe in recipe_capabilities():
            self.assertEqual(
                recipe["commands"],
                [commands_by_key[key] for key in recipe["command_keys"]],
            )
            self.assertTrue(recipe["expected_evidence"])

    def test_adapter_allowlist_is_derived_from_registry(self) -> None:
        registered = [item["command"] for item in command_capabilities()]

        self.assertEqual(SAFE_COMMANDS, registered)
        self.assertEqual(normalize_safe_command("  HF   SEARCH "), "hf search")
        self.assertIsNone(normalize_safe_command("hf mf dump"))
        self.assertIsNone(normalize_safe_command("lf t55xx write b 0 d DEADBEEF"))
        self.assertEqual(normalize_safe_command("HF EMV PSE -S2"), "emv pse -s2")
        self.assertEqual(normalize_safe_command("hf emv reader"), "emv reader")
        self.assertIsNone(normalize_safe_command("emv genac"))

    def test_emv_inspection_commands_do_not_use_obsolete_hf_prefix(self) -> None:
        emv_commands = [
            command
            for selector, command in command_selector_map("inspect").items()
            if selector.startswith("hf_emv_")
        ]

        self.assertTrue(emv_commands)
        self.assertTrue(all(command.startswith("emv ") for command in emv_commands))
        self.assertTrue(all(not command.startswith("hf emv ") for command in emv_commands))


if __name__ == "__main__":
    unittest.main()
