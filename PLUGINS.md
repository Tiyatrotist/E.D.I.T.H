# 🧩 E.D.I.T.H — Plugin Development Guide

EDITH features a modular **Drop-In Plugin Architecture** that allows developers to add custom capabilities and external tools with zero modifications to core system files.

---

## 🚀 How Plugins Work

1. Every valid `.py` file inside the `plugins/` directory is automatically discovered at startup.
2. The `PLUGIN` metadata dictionary within each file is registered into the LLM's Tool Declarations / Function Calling schema.
3. When the user speaks or types a relevant prompt, the LLM autonomously triggers the plugin and invokes its `run()` function.

---

## 📝 1. Creating a Basic Plugin

Create a new file inside the `plugins/` folder (for example: `plugins/currency_converter.py`):

```python
"""
plugins/currency_converter.py — Live Currency Rates Plugin
"""

PLUGIN = {
    "name": "get_exchange_rate",
    "description": (
        "Retrieves current exchange rates for USD, EUR, GBP, Gold, etc. "
        "Call this tool whenever the user asks about currency, rates, or foreign exchange."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "currency": {
                "type": "STRING",
                "description": "The currency code to check (e.g. USD, EUR, GBP, GOLD)"
            }
        },
        "required": ["currency"]
    }
}


def run(parameters: dict = None) -> str:
    """
    Main entrypoint invoked when the LLM triggers this tool.
    """
    params = parameters or {}
    currency = params.get("currency", "USD").upper()

    # Example rates or live API call
    rates = {
        "USD": "38.50 TRY",
        "EUR": "41.20 TRY",
        "GBP": "49.00 TRY",
        "GOLD": "3,450 TRY/Gram"
    }

    rate = rates.get(currency, "Currency code not found.")
    return f"Current rate for {currency}: {rate}"
```

---

## ⚙️ 2. Advanced Parameter Signatures

Your `run()` function can optionally accept additional context if needed:

```python
def run(parameters: dict = None, player=None, session_memory=None) -> str:
    # parameters: arguments provided by the LLM
    # session_memory: current conversation memory context
    ...
```

---

## 🛑 3. Enabling and Disabling Plugins

Plugins can be toggled without deleting files through `config/api_keys.json` or `memory/config_manager.py`:

```json
{
    "plugins": {
        "get_exchange_rate": true,
        "example_plugin": false
    }
}
```

---

## 🎯 4. Best Practices & Guidelines

- **Unique Snake_Case Name:** `PLUGIN["name"]` must match the regex `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$`.
- **Descriptive Prompts:** Make sure the `description` clearly explains when the LLM should invoke the tool, including explicit trigger words.
- **Robust Exception Handling:** If an unexpected exception occurs inside your plugin, `PluginRegistry` catches it gracefully to ensure the core assistant remains running.
