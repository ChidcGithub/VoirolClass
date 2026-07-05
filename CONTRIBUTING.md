# Contributing to VoirolClass

Thank you for your interest in contributing! Whether it's a bug report, new feature, code fix, or UI improvement, all contributions are welcome.

> [!IMPORTANT]
> By contributing, you agree that your contributions will be licensed under the [GNU General Public License v3.0](LICENSE).

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)
- [Pull Request Process](#pull-request-process)
- [Development Setup](#development-setup)
- [Coding Guidelines](#coding-guidelines)
- [Commit Messages](#commit-messages)
- [Testing](#testing)

---

## Code of Conduct

Please be respectful and constructive in all interactions. Harassment, trolling, and personal attacks will not be tolerated.

---

## How to Contribute

1. **Fork** the repository and create your branch from `main`.
2. **Make your changes** following the coding guidelines below.
3. **Test** your changes locally.
4. **Open a Pull Request** with a clear description of what you've done.

---

## Reporting Issues

When opening an issue, please use the provided issue template (if available) or include:

- **A clear, descriptive title**
- **Steps to reproduce** the issue (minimal, complete, and verifiable)
- **Expected behavior** and **actual behavior**
- **Environment details**:
  - Windows version (e.g., Windows 10 22H2, Windows 11 24H2)
  - Python version (`python --version`)
  - VoirolClass version (check `config.toml` or the About tab)
  - RAM and CPU info (relevant for performance issues)
- **Logs** — attach the latest log file from `%LOCALAPPDATA%\VoirolClass\logs\voirol.log`
- **Screenshots / screen recordings** if applicable

> [!TIP]
> Search [existing issues](https://github.com/ChidcGithub/VoirolClass/issues) before creating a new one to avoid duplicates.

---

## Feature Requests

Feature requests are welcome! Please include:

- **What problem** does this feature solve?
- **How would it work**? Describe the expected behavior.
- **Alternative solutions** you've considered.
- **Relevant context** (e.g., classroom scenario, hardware constraints).

---

## Pull Request Process

### Before You Submit

1. Ensure your PR addresses a single concern — avoid mixing unrelated changes.
2. Run the application locally and verify your changes work correctly.
3. Check for any debug/test code that should not be committed.
4. Rebase your branch on the latest `main` to keep history clean.

### PR Requirements

- **Title**: Short, descriptive, and prefixed with the area of change:

  | Prefix | Example |
  |--------|---------|
  | `feat:` | `feat: add dark mode support` |
  | `fix:` | `fix: VAD crash on empty audio chunk` |
  | `refactor:` | `refactor: extract APP_MAP to maps.py` |
  | `docs:` | `docs: update README badges` |
  | `style:` | `style: fix indentation in pipeline.py` |
  | `perf:` | `perf: reduce latency in audio pipeline` |
  | `i18n:` | `i18n: add Japanese translation` |
  | `chore:` | `chore: bump version to 0.2.3` |

- **Description**: Explain what your PR does and why. Include before/after behavior if applicable.
- **Related issues**: Reference any related issues with `Closes #123` or `Fixes #456`.
- **Screenshots**: For UI changes, include before/after screenshots.

### Review Process

1. A maintainer will review your PR within a few days.
2. Address any review comments by pushing additional commits.
3. Once approved, your PR will be squashed and merged.

---

## Development Setup

```bash
git clone https://github.com/ChidcGithub/VoirolClass.git
cd VoirolClass
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

To use the AI Agent or API features, copy `config.toml.example` to `config.toml` and fill in your API keys:

```toml
[ai]
enabled = true
api_key = "sk-your-key-here"
```

---

## Coding Guidelines

### Python

- Target **Python 3.10+**
- Follow **[PEP 8](https://peps.python.org/pep-0008/)** for code style
- Use **type hints** for all function signatures:

  ```python
  def process_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
      ...
  ```

- **Imports** order: standard library → third-party → project modules, separated by blank lines
- **Naming**:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- **Docstrings**: Not required for simple functions, but include them for public APIs and complex logic
- **Logging**: Use `get_logger(__name__)` at module level instead of `print()`

### Qt / GUI

- Keep UI logic out of model/code files — use signals and slots
- Use `t("key")` for all user-facing strings (internationalization)
- Prefer layout-based sizing over fixed geometry

### Agent Skills

Each skill function must:
- Accept a single `params: dict` argument
- Return a `str` result description
- Have a JSON schema for validation (see existing skills in `voirol/agent/skill_registry.py`)

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

[optional body]

[optional footer]
```

Examples:

```
fix: handle empty audio buffer in VAD

Avoid division by zero when no speech is detected.

Fixes #42
```

```
feat: add speaker enrollment via settings dialog

Teachers can now register by reading 5 sentences.
```

---

## Testing

This project does not yet have automated tests. For now, please manually verify:

1. **Audio pipeline**: Speech is detected, verified, and transcribed correctly
2. **Command matching**: All 3 tiers (exact, keyword, fuzzy) work as expected
3. **AI features** (if changed): Agent and semantic matcher produce correct results
4. **UI**: Settings dialog opens/closes, teacher profiles can be registered and selected
5. **No regressions**: Existing functionality still works after your changes

If you're adding a new feature, consider including a test script or manual test steps in your PR description.

---

## Questions?

If you're unsure about anything, feel free to open a [Discussion](https://github.com/ChidcGithub/VoirolClass/discussions) or ask in an issue. We're happy to help!
