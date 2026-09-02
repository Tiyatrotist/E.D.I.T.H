# Contributing to E.D.I.T.H

Thank you for your interest in contributing to **E.D.I.T.H**!

E.D.I.T.H is an advanced, privacy-first personal AI assistant and desktop agent for Windows. Contributions should preserve the project's flexible design, clean documentation, and robust offline capabilities while expanding its multi-provider capabilities.

---

## 🎯 Ways to Contribute

We welcome contributions across various areas:
1. **Drop-in Plugins:** Build and share new plugins in the `plugins/` folder (see [PLUGINS.md](PLUGINS.md)).
2. **Action Modules:** Enhance built-in tools in `actions/` (automation, vision, hardware, communication).
3. **LLM Providers:** Extend `core/llm_pool.py` with support for additional inference backends.
4. **Testing & QA:** Write automated tests for tools, date parsers, and API fallback chains.
5. **UI & Web Dashboard:** Improve the CustomTkinter desktop interface or the FastAPI web control panel.
6. **Documentation:** Refine setup guides, docstrings, and translation files.

---

## 📋 Development Principles

- **Clean & Documented Code:** Every module should have clear docstrings, type annotations where practical, and informative debug logs.
- **Privacy-First:** Never commit credentials, personal phone numbers, machine-specific paths, or secret keys.
- **Safe Execution:** Keep shell commands, file modifications, and automation boundaries safe and predictable.
- **Cross-Provider Compatibility:** Features should work with both local models (Ollama) and cloud APIs (Gemini, OpenAI, Claude).

---

## 🚀 Pull Request Workflow

1. Fork the repository and create a feature branch (`git checkout -b feature/my-new-tool`).
2. Implement your changes following existing code conventions.
3. Test your changes locally (`python main.py` or isolated module verification).
4. Commit your changes with clear messages (`git commit -m 'feat: add exchange rate plugin'`).
5. Push to your branch and open a Pull Request.

---

## 🧪 Testing Guidelines

Verify that all modules load properly before submitting PRs:
```bash
python -c "
from core.llm_pool import LLMPool
from core.plugin_loader import discover_plugins
from actions.web_search import web_search
print('Verification passed!')
"
```
