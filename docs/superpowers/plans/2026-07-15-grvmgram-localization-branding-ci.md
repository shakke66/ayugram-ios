# GRVMgram Localization, Branding, and Final CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Localize every GRVMgram-specific user-facing string in Russian with an English fallback, remove every public AyuGram project reference, finish public GRVMgram branding, and make the final GitHub Actions run prove that it produced a valid sideloadable `GRVMgram.ipa`.

**Architecture:** Add a small resource-backed localizer to `TelegramPresentationData`, because Telegram's selected language is represented by `PresentationStrings.baseLanguageCode` while non-English Telegram strings are downloaded from the server. Keep all internal `AyuGram*` modules, hooks, Codable keys, and the legacy database filename unchanged; only public strings, links, metadata, and artifact names change. A Python standard-library validator enforces localization parity, public-brand rules, and IPA structure both on Windows and in GitHub Actions.

**Tech Stack:** Swift 5, Foundation `Bundle`/`NSDictionary`, Telegram `PresentationStrings`, Bazel/Starlark, Python 3.12 standard library (`argparse`, `json`, `plistlib`, `re`, `unittest`, `zipfile`), GitHub Actions, GitHub CLI.

## Global Constraints

- Work only on branch `codex/grvmgram-full-parity` until the complete implementation has passed local checks.
- Do not modify, revert, stage, or reformat the existing uncommitted Ghost fix in `submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift` while executing localization tasks.
- Run localization and branding after the feature tasks have created their final screens, menus, alerts, and archive/history flows.
- Russian applies only to GRVMgram-specific UI; Telegram's normal language selection remains authoritative for stock Telegram UI.
- English is the fallback for every Telegram language other than Russian.
- Do not add third-party packages, generated localization frameworks, YAML parsers, or icon-generation dependencies.
- Preserve internal `AyuGramHooks`, module/type names, `.ayuGramSettings`, Codable keys, `com.ayugram.deletedMessagesDB`, and `ayugram_messages.db`.
- Remove the About/Project/Links UI instead of replacing it with a GRVMgram promotional page.
- Remove AyuGram channels, chats, documentation, GitHub, Crowdin, Boosty, crypto addresses, and original-project donation links from runtime UI.
- Keep the current icon asset IDs and Bazel target `Telegram`; do not rename `Telegram.icon`, `*.alticon`, `Telegram.app`, or the internal Bazel-produced `Telegram.ipa`.
- Publish the external artifact as `GRVMgram.ipa` in artifact `GRVMgram-ipa`.
- Do not trigger intermediate GitHub Actions builds. Push `master` only after all Windows checks pass.
- A green workflow without a validated IPA is a failure; missing or malformed IPA must make the workflow exit non-zero.

---

## File Map

### Create

- `submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift` - language selection, resource loading, English fallback, and formatted-string lookup.
- `Telegram/Telegram-iOS/en.lproj/GRVMgram.strings` - canonical English values.
- `Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings` - complete Russian values with the same keys and format tokens.
- `build-system/Make/ValidateGRVMgram.py` - source and IPA validator used locally and in CI.
- `Tests/GRVMgramValidation/test_validate_grvmgram.py` - standard-library unit tests, including synthetic IPA fixtures.

### Modify

- `Telegram/BUILD:251-258` - package the two `GRVMgram.strings` resources.
- `submodules/AyuGramSettingsUI/Sources/AyuGramMainController.swift:24-165` - remove header/project links and localize functional navigation.
- `submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift:186-267,414` - localize Ghost/spy/premium settings.
- `submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift:105-245` - localize filters and editors.
- `submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift:110-193` - localize providers, general settings, webview, and confirmations.
- `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift:118-212` - localize appearance and icon choices; remove Desktop Drawer rows.
- `submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift:158-321` - localize chat controls, marks, modes, and editors.
- `submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift:60-112` - localize the account archive.
- `submodules/AyuGramSettingsUI/Sources/AyuGramEditedMessagesController.swift:60-113` - localize revision archive/history.
- `submodules/AyuGramSettingsUI/Sources/AyuGramShadowBanController.swift:64-124` - localize the Shadow Ban editor.
- `submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift:14-166` - remove donations/dead link association and localize crash/reset UI.
- `submodules/TelegramUI/Sources/ChatController.swift:2249-2256,2419-2427` - localize sticker/GIF confirmations.
- `submodules/TelegramUI/Sources/Chat/ChatControllerMediaRecording.swift:690-699` - localize voice confirmation.
- `submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryContainerScreen.swift:1082-1093` - localize the pre-view Ghost prompt implemented by the parity task.
- `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoSettingsItems.swift:254-256` - show the localized GRVMgram settings row.
- `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift` - localize GRVMgram History and parity context actions added by earlier tasks.
- `submodules/TelegramUI/Sources/AppDelegate.swift:1038` - rebrand the icon error log.
- `Telegram/BUILD:609-617,938-948,1030-1040,1137-1147,1250-1260,1381-1391,1475-1485,1538-1558,1691` - public app/extension metadata.
- `Telegram/Telegram-iOS/Config-Fork.xcconfig:1` - manual fork build display name.
- `Telegram/Telegram-iOS/ar.lproj/InfoPlist.strings:2` - remove the localized display-name override.
- `Telegram/Telegram-iOS/ko.lproj/InfoPlist.strings:2` - remove the localized display-name override.
- `.github/workflows/build.yml:13-157` - source tests, hard IPA failure, IPA validation, and GRVMgram artifact name.

---

### Task 1: Add the Cross-Platform Validation Harness

**Files:**
- Create: `Tests/GRVMgramValidation/test_validate_grvmgram.py`
- Create: `build-system/Make/ValidateGRVMgram.py`

**Interfaces:**
- Produces: `ValidationError`.
- Produces: `parse_strings(path: pathlib.Path) -> dict[str, str]`.
- Produces: `validate_localizations(root: pathlib.Path) -> None`.
- Produces: `validate_public_branding(root: pathlib.Path) -> None`.
- Produces: `validate_metadata(root: pathlib.Path) -> None`.
- Produces: `validate_workflow(root: pathlib.Path) -> None`.
- Produces: `validate_source(root: pathlib.Path) -> None`.
- Produces: `validate_ipa(path: pathlib.Path) -> dict[str, str]`.
- Consumes: no project Swift code, no third-party Python packages.

- [ ] **Step 1: Write the failing validator unit tests**

Create `Tests/GRVMgramValidation/test_validate_grvmgram.py`:

```python
from __future__ import annotations

import importlib.util
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPOSITORY_ROOT / "build-system" / "Make" / "ValidateGRVMgram.py"
SPEC = importlib.util.spec_from_file_location("validate_grvmgram", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def strings_file(entries: dict[str, str]) -> str:
    return "\n".join(
        f'"{key}" = "{value}";' for key, value in entries.items()
    ) + "\n"


def create_localization_tree(root: Path, russian_extra: bool = False) -> None:
    entries = {
        "GRVMgram.Brand.Name": "GRVMgram",
        "GRVMgram.Chat.DeletedMark.Default": "🧹",
        "GRVMgram.Chat.EditedMark.Default": "edited",
        "GRVMgram.Ghost.ActiveCount": "%d/5 enabled",
    }
    russian = dict(entries)
    russian["GRVMgram.Chat.EditedMark.Default"] = "изменено"
    russian["GRVMgram.Ghost.ActiveCount"] = "%d/5 включено"
    if russian_extra:
        russian["GRVMgram.Extra"] = "лишнее"

    write(
        root / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings",
        strings_file(entries),
    )
    write(
        root / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings",
        strings_file(russian),
    )
    enum_cases = "\n".join(
        f'    case key{index} = "{key}"'
        for index, key in enumerate(entries)
    )
    write(
        root
        / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift",
        "public enum GRVMgramStringKey: String, CaseIterable {\n"
        + enum_cases
        + "\n}\n",
    )


def create_ipa(
    path: Path,
    *,
    display_name: str = "GRVMgram",
    bundle_name: str = "GRVMgram",
    include_payload: bool = True,
    include_executable: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if not include_payload:
            archive.writestr("README.txt", b"not an ipa")
            return
        app_root = "Payload/Telegram.app"
        info = {
            "CFBundleDisplayName": display_name,
            "CFBundleName": bundle_name,
            "CFBundleExecutable": "Telegram",
            "CFBundleIdentifier": "ph.telegra.Telegraph",
            "CFBundleShortVersionString": "12.6.2",
            "CFBundleVersion": "3000",
        }
        archive.writestr(f"{app_root}/Info.plist", plistlib.dumps(info))
        if include_executable:
            archive.writestr(f"{app_root}/Telegram", b"Mach-O fixture")
        resources = {
            "GRVMgram.Brand.Name": "GRVMgram",
            "GRVMgram.Chat.DeletedMark.Default": "🧹",
        }
        archive.writestr(
            f"{app_root}/en.lproj/GRVMgram.strings",
            strings_file(resources).encode("utf-8"),
        )
        archive.writestr(
            f"{app_root}/ru.lproj/GRVMgram.strings",
            strings_file(resources).encode("utf-8"),
        )


class StringsTests(unittest.TestCase):
    def test_parse_strings_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.strings"
            write(path, '"A" = "one";\n"A" = "two";\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "duplicate key A"):
                VALIDATOR.parse_strings(path)

    def test_localizations_require_identical_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root, russian_extra=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_accept_matching_keys_and_format_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            VALIDATOR.validate_localizations(root)


class BrandingTests(unittest.TestCase):
    def test_legacy_database_literals_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift",
                'let queue = "com.ayugram.deletedMessagesDB"\n'
                'let path = "ayugram_messages.db"\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_original_project_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Bad.swift",
                'let url = "https://t.me/ayugram"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "forbidden public token"):
                VALIDATOR.validate_public_branding(root)


class IpaTests(unittest.TestCase):
    def test_valid_ipa_returns_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path)
            metadata = VALIDATOR.validate_ipa(path)
            self.assertEqual(metadata["display_name"], "GRVMgram")
            self.assertEqual(metadata["bundle_id"], "ph.telegra.Telegraph")
            self.assertEqual(metadata["version"], "12.6.2")
            self.assertEqual(metadata["build"], "3000")

    def test_missing_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, include_payload=False)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Payload/.+Info.plist"):
                VALIDATOR.validate_ipa(path)

    def test_wrong_display_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, display_name="Telegram")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "CFBundleDisplayName"):
                VALIDATOR.validate_ipa(path)

    def test_missing_executable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, include_executable=False)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "executable"):
                VALIDATOR.validate_ipa(path)

    def test_corrupt_zip_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            path.write_bytes(b"not a zip")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "valid ZIP"):
                VALIDATOR.validate_ipa(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
```

Expected: non-zero exit; import fails because `build-system/Make/ValidateGRVMgram.py` does not exist.

- [ ] **Step 3: Implement the validator with the standard library**

Create `build-system/Make/ValidateGRVMgram.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import sys
import zipfile
from pathlib import Path


class ValidationError(Exception):
    pass


STRINGS_ENTRY_RE = re.compile(
    r'^\s*"((?:\\.|[^"\\])*)"\s*=\s*"((?:\\.|[^"\\])*)"\s*;\s*$'
)
SWIFT_ENUM_KEY_RE = re.compile(
    r'case\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*"([^"]+)"'
)
SWIFT_STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
FORMAT_TOKEN_RE = re.compile(r'%(?:\d+\$)?[@diuf]')
LETTER_RE = re.compile(r'[A-Za-z\u0400-\u04ff]')
INTERPOLATION_RE = re.compile(r'\\\([^)]*\)')
UNICODE_ESCAPE_RE = re.compile(r'\\u\{[0-9A-Fa-f]+\}')

FORBIDDEN_PUBLIC_TOKENS = (
    "https://t.me/ayugram",
    "https://t.me/ayugramchat",
    "https://docs.ayugram.one",
    "docs.ayugram.one",
    "https://boosty.to/ayugram",
    "github.com/AyuGram",
    "crowdin.com/project/ayugram",
    "@ayugram",
    "@ayugramchat",
    "UQA4i8U8vP3mYUZSV3KqDQEHPwmhninEqCkkKc7BITQ652de",
    "bc1qdk6qq4mzq5yap3fpy0qau3246w3m3uwac9f0xd",
    "0x405589857C8DFAb45B2027c68ad1e58877FDa347",
    "8ZHQpPxpsdRjsWoBcF1dmvRM5dB6zEhJ3jMBFZjYfyHs",
    "TRpbajq38qU8joThgAfKJLyEPbNjzsdPJ1",
)
ALLOWED_INTERNAL_AYUGRAM_LITERALS = {
    "com.ayugram.deletedMessagesDB",
    "ayugram_messages.db",
}
ALLOWED_SETTINGS_UI_LITERALS = {
    "",
    "default",
    "Black",
    "BlackClassic",
    "BlackFilled",
    "Blue",
    "BlueClassic",
    "BlueFilled",
    "WhiteFilled",
    "New1",
    "New2",
    "Premium",
    "PremiumBlack",
    "PremiumTurbo",
    "Menlo",
    "Courier",
    "Courier-Bold",
}
FORBIDDEN_CROSS_UI_LITERALS = {
    "Send sticker?",
    "Send GIF?",
    "Send voice message?",
    "Enable Ghost Mode to view stories privately",
    "AyuGram Settings",
}
RUNTIME_ROOTS = (
    "submodules/AyuGramSettingsUI",
    "submodules/AyuGramLib",
    "submodules/AyuGramFeatures",
    "submodules/TelegramUI",
    "Telegram/Telegram-iOS",
)
TEXT_SUFFIXES = {".swift", ".m", ".mm", ".plist", ".strings", ".xcconfig"}


def read_utf8(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{path}: not strict UTF-8: {error}") from error
    if "\ufffd" in value:
        raise ValidationError(f"{path}: contains U+FFFD replacement character")
    return value


def decode_strings_value(value: str, path: Path, line_number: int) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"{path}:{line_number}: invalid escaped string: {error}"
        ) from error


def parse_strings_text(value: str, source: str) -> dict[str, str]:
    result: dict[str, str] = {}
    in_block_comment = False
    for line_number, line in enumerate(value.splitlines(), start=1):
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if not stripped or stripped.startswith("//"):
            continue
        if stripped.startswith("/*"):
            in_block_comment = "*/" not in stripped
            continue
        match = STRINGS_ENTRY_RE.fullmatch(line)
        if match is None:
            raise ValidationError(f"{source}:{line_number}: invalid .strings entry")
        path = Path(source)
        key = decode_strings_value(match.group(1), path, line_number)
        localized = decode_strings_value(match.group(2), path, line_number)
        if key in result:
            raise ValidationError(f"{source}:{line_number}: duplicate key {key}")
        result[key] = localized
    if in_block_comment:
        raise ValidationError(f"{source}: unterminated block comment")
    return result


def parse_strings(path: Path) -> dict[str, str]:
    return parse_strings_text(read_utf8(path), str(path))


def format_tokens(value: str) -> list[str]:
    without_percent_literals = value.replace("%%", "")
    return FORMAT_TOKEN_RE.findall(without_percent_literals)


def validate_localizations(root: Path) -> None:
    english_path = root / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
    russian_path = root / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"
    enum_path = (
        root
        / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
    )
    for path in (english_path, russian_path, enum_path):
        if not path.is_file():
            raise ValidationError(f"missing required file: {path}")

    english = parse_strings(english_path)
    russian = parse_strings(russian_path)
    if set(english) != set(russian):
        missing_ru = sorted(set(english) - set(russian))
        extra_ru = sorted(set(russian) - set(english))
        raise ValidationError(
            f"localization key mismatch: missing_ru={missing_ru}, extra_ru={extra_ru}"
        )

    enum_keys = set(SWIFT_ENUM_KEY_RE.findall(read_utf8(enum_path)))
    if enum_keys != set(english):
        missing_enum = sorted(set(english) - enum_keys)
        extra_enum = sorted(enum_keys - set(english))
        raise ValidationError(
            f"Swift key mismatch: missing_enum={missing_enum}, extra_enum={extra_enum}"
        )

    for key in sorted(english):
        if not english[key]:
            raise ValidationError(f"{english_path}: empty value for {key}")
        if not russian[key]:
            raise ValidationError(f"{russian_path}: empty value for {key}")
        if format_tokens(english[key]) != format_tokens(russian[key]):
            raise ValidationError(
                f"format-token mismatch for {key}: "
                f"{format_tokens(english[key])} != {format_tokens(russian[key])}"
            )

    required_values = {
        "GRVMgram.Brand.Name": ("GRVMgram", "GRVMgram"),
        "GRVMgram.Chat.DeletedMark.Default": ("🧹", "🧹"),
        "GRVMgram.Chat.EditedMark.Default": ("edited", "изменено"),
    }
    for key, expected in required_values.items():
        actual = (english.get(key), russian.get(key))
        if actual != expected:
            raise ValidationError(f"unexpected values for {key}: {actual}")


def iter_runtime_files(root: Path):
    for relative_root in RUNTIME_ROOTS:
        directory = root / relative_root
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                yield path
    build_file = root / "Telegram/BUILD"
    if build_file.is_file():
        yield build_file


def validate_settings_ui_literals(root: Path) -> None:
    directory = root / "submodules/AyuGramSettingsUI/Sources"
    if not directory.exists():
        return
    violations: list[str] = []
    for path in directory.glob("*.swift"):
        for line_number, line in enumerate(read_utf8(path).splitlines(), start=1):
            for raw_literal in SWIFT_STRING_RE.findall(line):
                if raw_literal in ALLOWED_SETTINGS_UI_LITERALS:
                    continue
                scrubbed = INTERPOLATION_RE.sub("", raw_literal)
                scrubbed = UNICODE_ESCAPE_RE.sub("", scrubbed)
                if LETTER_RE.search(scrubbed):
                    violations.append(f"{path}:{line_number}: {raw_literal}")
    if violations:
        raise ValidationError(
            "hard-coded GRVMgram Settings UI text:\n" + "\n".join(violations)
        )


def validate_public_branding(root: Path) -> None:
    violations: list[str] = []
    for path in iter_runtime_files(root):
        value = read_utf8(path)
        for token in FORBIDDEN_PUBLIC_TOKENS:
            if token.casefold() in value.casefold():
                violations.append(f"{path}: forbidden public token {token}")
        if path.suffix in {".swift", ".m", ".mm"}:
            for line_number, line in enumerate(value.splitlines(), start=1):
                for literal in SWIFT_STRING_RE.findall(line):
                    if "ayugram" not in literal.casefold():
                        continue
                    if literal in ALLOWED_INTERNAL_AYUGRAM_LITERALS:
                        continue
                    violations.append(
                        f"{path}:{line_number}: public/loggable AyuGram literal {literal}"
                    )
                for forbidden in FORBIDDEN_CROSS_UI_LITERALS:
                    if forbidden in line:
                        violations.append(
                            f"{path}:{line_number}: hard-coded UI text {forbidden}"
                        )
    if violations:
        raise ValidationError("\n".join(violations))
    validate_settings_ui_literals(root)


def validate_metadata(root: Path) -> None:
    build_path = root / "Telegram/BUILD"
    build = read_utf8(build_path)
    if build.count("<string>GRVMgram</string>") < 9:
        raise ValidationError(
            f"{build_path}: expected at least 9 GRVMgram plist values"
        )
    if "<string>Telegram</string>" in build:
        raise ValidationError(f"{build_path}: public extension name is still Telegram")
    if "<string>GRVMgram Color Theme File</string>" not in build:
        raise ValidationError(f"{build_path}: theme file description is not branded")

    config_path = root / "Telegram/Telegram-iOS/Config-Fork.xcconfig"
    config = read_utf8(config_path)
    if re.search(r"(?m)^APP_NAME\s*=\s*GRVMgram\s*$", config) is None:
        raise ValidationError(f"{config_path}: expected APP_NAME=GRVMgram")

    for language in ("ar", "ko"):
        path = root / f"Telegram/Telegram-iOS/{language}.lproj/InfoPlist.strings"
        value = read_utf8(path)
        if "CFBundleDisplayName" in value:
            raise ValidationError(f"{path}: remove CFBundleDisplayName override")


def validate_workflow(root: Path) -> None:
    path = root / ".github/workflows/build.yml"
    value = read_utf8(path)
    required = (
        "Validate GRVMgram sources",
        "python3 -m unittest discover -s Tests/GRVMgramValidation",
        "python3 build-system/Make/ValidateGRVMgram.py source",
        'cp -L "$IPA" "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"',
        'test -s "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"',
        "Validate GRVMgram IPA",
        "python3 build-system/Make/ValidateGRVMgram.py ipa artifacts/GRVMgram.ipa",
        "name: GRVMgram-ipa",
        "path: artifacts/GRVMgram.ipa",
        "if-no-files-found: error",
    )
    missing = [item for item in required if item not in value]
    if missing:
        raise ValidationError(f"{path}: missing workflow contracts: {missing}")
    if "name: Telegram-ipa" in value:
        raise ValidationError(f"{path}: legacy public artifact name remains")


def validate_source(root: Path) -> None:
    validate_localizations(root)
    validate_public_branding(root)
    validate_metadata(root)
    validate_workflow(root)


def validate_ipa(path: Path) -> dict[str, str]:
    if path.name != "GRVMgram.ipa":
        raise ValidationError(f"artifact must be named GRVMgram.ipa, got {path.name}")
    if not path.is_file() or path.stat().st_size == 0:
        raise ValidationError(f"IPA is missing or empty: {path}")
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise ValidationError(f"IPA is not a valid ZIP: {error}") from error

    with archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValidationError(f"IPA contains corrupt member: {bad_member}")
        names = archive.namelist()
        info_paths = [
            name
            for name in names
            if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", name)
        ]
        if len(info_paths) != 1:
            raise ValidationError(
                f"expected exactly one Payload/*.app/Info.plist, got {info_paths}"
            )
        info_path = info_paths[0]
        try:
            info = plistlib.loads(archive.read(info_path))
        except (KeyError, plistlib.InvalidFileException) as error:
            raise ValidationError(f"invalid app Info.plist: {error}") from error

        if info.get("CFBundleDisplayName") != "GRVMgram":
            raise ValidationError(
                f"CFBundleDisplayName is {info.get('CFBundleDisplayName')!r}"
            )
        if info.get("CFBundleName") != "GRVMgram":
            raise ValidationError(f"CFBundleName is {info.get('CFBundleName')!r}")

        app_root = info_path.removesuffix("Info.plist")
        executable = info.get("CFBundleExecutable")
        executable_path = f"{app_root}{executable}" if executable else ""
        if not executable or executable_path not in names:
            raise ValidationError(f"missing main app executable {executable_path!r}")
        if archive.getinfo(executable_path).file_size == 0:
            raise ValidationError("main app executable is empty")

        localized_tables: dict[str, dict[str, str]] = {}
        for language in ("en", "ru"):
            resource_path = f"{app_root}{language}.lproj/GRVMgram.strings"
            if resource_path not in names:
                raise ValidationError(f"missing IPA resource {resource_path}")
            try:
                resource_text = archive.read(resource_path).decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValidationError(
                    f"{resource_path}: not strict UTF-8: {error}"
                ) from error
            localized_tables[language] = parse_strings_text(
                resource_text, resource_path
            )
        if set(localized_tables["en"]) != set(localized_tables["ru"]):
            raise ValidationError("IPA English/Russian localization key mismatch")

        return {
            "display_name": str(info["CFBundleDisplayName"]),
            "bundle_name": str(info["CFBundleName"]),
            "bundle_id": str(info.get("CFBundleIdentifier", "")),
            "version": str(info.get("CFBundleShortVersionString", "")),
            "build": str(info.get("CFBundleVersion", "")),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ValidateGRVMgram")
    subparsers = parser.add_subparsers(dest="command", required=True)
    source_parser = subparsers.add_parser("source")
    source_parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    ipa_parser = subparsers.add_parser("ipa")
    ipa_parser.add_argument("path", type=Path)
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "source":
            validate_source(arguments.root.resolve())
            print("GRVMgram source validation passed")
        else:
            metadata = validate_ipa(arguments.path.resolve())
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
    except ValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the validator unit tests and verify GREEN**

Run:

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
python -m py_compile build-system/Make/ValidateGRVMgram.py
```

Expected: 10 tests report `OK`; `py_compile` exits 0 with no output.

- [ ] **Step 5: Commit the validation harness without staging the Ghost file**

```powershell
git add -- build-system/Make/ValidateGRVMgram.py Tests/GRVMgramValidation/test_validate_grvmgram.py
git diff --cached --check
git commit -m "test: add GRVMgram release validators"
```

Expected: staged diff contains only the two validator files; commit succeeds.

---

### Task 2: Add Resource-Backed English/Russian Localization

**Files:**
- Create: `Telegram/Telegram-iOS/en.lproj/GRVMgram.strings`
- Create: `Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings`
- Create: `submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift`
- Modify: `Telegram/BUILD:251-258`
- Modify: `Tests/GRVMgramValidation/test_validate_grvmgram.py`

**Interfaces:**
- Produces: `GRVMgramStringKey: String, CaseIterable`.
- Produces: `GRVMgramStrings.init(_ presentationStrings: PresentationStrings)`.
- Produces: `GRVMgramStrings.languageCode: String`.
- Produces: `GRVMgramStrings.subscript(_ key: GRVMgramStringKey) -> String`.
- Produces: `GRVMgramStrings.format(_ key: GRVMgramStringKey, _ arguments: CVarArg...) -> String`.
- Consumes: `PresentationStrings.baseLanguageCode` and `getAppBundle()`.
- Consumes: the exact, equal key sets in both `GRVMgram.strings` files.

- [ ] **Step 1: Add a failing repository-level localization contract test**

Add this method to `StringsTests` in `Tests/GRVMgramValidation/test_validate_grvmgram.py`:

```python
    def test_repository_localizations_are_complete(self) -> None:
        VALIDATOR.validate_localizations(REPOSITORY_ROOT)
```

- [ ] **Step 2: Run only the repository localization test and verify RED**

```powershell
python Tests/GRVMgramValidation/test_validate_grvmgram.py StringsTests.test_repository_localizations_are_complete -v
```

Expected: FAIL with `missing required file` naming `en.lproj/GRVMgram.strings`.

- [ ] **Step 3: Create the typed localization keys**

Create `submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift` with one case per resource key. The baseline key set is:

```swift
import Foundation
import AppBundle

public enum GRVMgramStringKey: String, CaseIterable {
    case brandName = "GRVMgram.Brand.Name"
    case settingsTitle = "GRVMgram.Settings.Title"
    case mainCore = "GRVMgram.Main.Core"
    case mainFilters = "GRVMgram.Main.Filters"
    case mainGeneral = "GRVMgram.Main.General"
    case mainAppearance = "GRVMgram.Main.Appearance"
    case mainChats = "GRVMgram.Main.Chats"
    case mainOther = "GRVMgram.Main.Other"
    case mainDeleted = "GRVMgram.Main.Deleted"
    case mainHistory = "GRVMgram.Main.History"

    case commonDefault = "GRVMgram.Common.Default"
    case commonOff = "GRVMgram.Common.Off"
    case commonHidden = "GRVMgram.Common.Hidden"
    case commonShown = "GRVMgram.Common.Shown"
    case commonWithModifier = "GRVMgram.Common.WithModifier"
    case commonNever = "GRVMgram.Common.Never"
    case commonInGhost = "GRVMgram.Common.InGhost"
    case commonAlways = "GRVMgram.Common.Always"
    case commonSearch = "GRVMgram.Common.Search"
    case commonClear = "GRVMgram.Common.Clear"
    case commonExport = "GRVMgram.Common.Export"
    case commonImport = "GRVMgram.Common.Import"

    case coreTitle = "GRVMgram.Core.Title"
    case ghostHeader = "GRVMgram.Ghost.Header"
    case ghostMaster = "GRVMgram.Ghost.Master"
    case ghostReadReceipts = "GRVMgram.Ghost.ReadReceipts"
    case ghostStoryViews = "GRVMgram.Ghost.StoryViews"
    case ghostOnline = "GRVMgram.Ghost.Online"
    case ghostTyping = "GRVMgram.Ghost.Typing"
    case ghostUpload = "GRVMgram.Ghost.Upload"
    case ghostAutoOffline = "GRVMgram.Ghost.AutoOffline"
    case ghostReadOnAction = "GRVMgram.Ghost.ReadOnAction"
    case ghostReadOnActionInfo = "GRVMgram.Ghost.ReadOnAction.Info"
    case ghostStoryPrompt = "GRVMgram.Ghost.StoryPrompt"
    case ghostStoryPromptInfo = "GRVMgram.Ghost.StoryPrompt.Info"
    case ghostSchedule = "GRVMgram.Ghost.Schedule"
    case ghostScheduleInfo = "GRVMgram.Ghost.Schedule.Info"
    case ghostSilent = "GRVMgram.Ghost.Silent"
    case ghostSilentInfo = "GRVMgram.Ghost.Silent.Info"
    case ghostActiveCount = "GRVMgram.Ghost.ActiveCount"
    case spyHeader = "GRVMgram.Spy.Header"
    case spySaveDeleted = "GRVMgram.Spy.SaveDeleted"
    case spySaveEdits = "GRVMgram.Spy.SaveEdits"
    case spySaveBots = "GRVMgram.Spy.SaveBots"
    case coreOtherHeader = "GRVMgram.Core.Other.Header"
    case coreLocalPremium = "GRVMgram.Core.LocalPremium"
    case coreDisableAds = "GRVMgram.Core.DisableAds"

    case filtersTitle = "GRVMgram.Filters.Title"
    case filtersHeader = "GRVMgram.Filters.Header"
    case filtersEnable = "GRVMgram.Filters.Enable"
    case filtersInChats = "GRVMgram.Filters.InChats"
    case filtersBlocked = "GRVMgram.Filters.Blocked"
    case filtersPatterns = "GRVMgram.Filters.Patterns"
    case filtersAdd = "GRVMgram.Filters.Add"
    case filtersAddPrompt = "GRVMgram.Filters.AddPrompt"
    case filtersEditPrompt = "GRVMgram.Filters.EditPrompt"
    case filtersReversed = "GRVMgram.Filters.Reversed"
    case filtersAddReversed = "GRVMgram.Filters.AddReversed"
    case filtersAddReversedPrompt = "GRVMgram.Filters.AddReversedPrompt"
    case filtersEditReversedPrompt = "GRVMgram.Filters.EditReversedPrompt"
    case filtersGlobal = "GRVMgram.Filters.Global"
    case filtersCaseSensitive = "GRVMgram.Filters.CaseSensitive"
    case filtersType = "GRVMgram.Filters.Type"
    case filtersButton = "GRVMgram.Filters.Button"
    case filtersSelectChat = "GRVMgram.Filters.SelectChat"
    case filtersShowFiltered = "GRVMgram.Filters.ShowFiltered"
    case filtersHideFiltered = "GRVMgram.Filters.HideFiltered"
    case filtersClear = "GRVMgram.Filters.Clear"
    case shadowTitle = "GRVMgram.Shadow.Title"
    case shadowIds = "GRVMgram.Shadow.IDs"
    case shadowAdd = "GRVMgram.Shadow.Add"
    case shadowAddPrompt = "GRVMgram.Shadow.AddPrompt"
    case shadowEditPrompt = "GRVMgram.Shadow.EditPrompt"

    case generalTitle = "GRVMgram.General.Title"
    case translationHeader = "GRVMgram.Translation.Header"
    case translationProvider = "GRVMgram.Translation.Provider"
    case translationTelegram = "GRVMgram.Translation.Telegram"
    case translationGoogle = "GRVMgram.Translation.Google"
    case translationYandex = "GRVMgram.Translation.Yandex"
    case translationNative = "GRVMgram.Translation.Native"
    case generalHeader = "GRVMgram.General.Header"
    case generalHideStories = "GRVMgram.General.HideStories"
    case generalSimilarChannels = "GRVMgram.General.SimilarChannels"
    case generalNotificationDelay = "GRVMgram.General.NotificationDelay"
    case generalSeconds = "GRVMgram.General.Seconds"
    case generalPeerId = "GRVMgram.General.PeerID"
    case generalZalgo = "GRVMgram.General.Zalgo"
    case generalLinkPreviews = "GRVMgram.General.LinkPreviews"
    case generalLinkWarning = "GRVMgram.General.LinkWarning"
    case peerIdApi = "GRVMgram.General.PeerID.API"
    case peerIdBotApi = "GRVMgram.General.PeerID.BotAPI"
    case webviewHeader = "GRVMgram.Webview.Header"
    case webviewAndroid = "GRVMgram.Webview.Android"
    case webviewHeight = "GRVMgram.Webview.Height"
    case webviewWidth = "GRVMgram.Webview.Width"
    case confirmationsHeader = "GRVMgram.Confirmations.Header"
    case confirmationsSticker = "GRVMgram.Confirmations.Sticker"
    case confirmationsGif = "GRVMgram.Confirmations.GIF"
    case confirmationsVoice = "GRVMgram.Confirmations.Voice"

    case appearanceTitle = "GRVMgram.Appearance.Title"
    case appIconHeader = "GRVMgram.AppIcon.Header"
    case appIconTitle = "GRVMgram.AppIcon.Title"
    case appIconBlack = "GRVMgram.AppIcon.Black"
    case appIconBlackClassic = "GRVMgram.AppIcon.BlackClassic"
    case appIconBlackFilled = "GRVMgram.AppIcon.BlackFilled"
    case appIconBlue = "GRVMgram.AppIcon.Blue"
    case appIconBlueClassic = "GRVMgram.AppIcon.BlueClassic"
    case appIconBlueFilled = "GRVMgram.AppIcon.BlueFilled"
    case appIconWhiteFilled = "GRVMgram.AppIcon.WhiteFilled"
    case appIconNew1 = "GRVMgram.AppIcon.New1"
    case appIconNew2 = "GRVMgram.AppIcon.New2"
    case appIconPremium = "GRVMgram.AppIcon.Premium"
    case appIconPremiumBlack = "GRVMgram.AppIcon.PremiumBlack"
    case appIconPremiumTurbo = "GRVMgram.AppIcon.PremiumTurbo"
    case appearanceHideBadge = "GRVMgram.Appearance.HideBadge"
    case appearanceHideCounters = "GRVMgram.Appearance.HideCounters"
    case appearanceHeader = "GRVMgram.Appearance.Header"
    case appearanceMd3 = "GRVMgram.Appearance.MD3"
    case appearanceTail = "GRVMgram.Appearance.Tail"
    case appearanceBackgrounds = "GRVMgram.Appearance.Backgrounds"
    case appearanceCodeFont = "GRVMgram.Appearance.CodeFont"
    case appearanceAvatarCorners = "GRVMgram.Appearance.AvatarCorners"
    case appearanceBubbleRadius = "GRVMgram.Appearance.BubbleRadius"
    case appearanceSingleCorner = "GRVMgram.Appearance.SingleCorner"
    case appearancePremiumStatuses = "GRVMgram.Appearance.PremiumStatuses"
    case appearanceFolders = "GRVMgram.Appearance.Folders"
    case appearanceFolderCounters = "GRVMgram.Appearance.FolderCounters"
    case appearanceAllChats = "GRVMgram.Appearance.AllChats"

    case chatsTitle = "GRVMgram.Chats.Title"
    case stickersHeader = "GRVMgram.Chats.Stickers.Header"
    case stickersOnlyAdded = "GRVMgram.Chats.Stickers.OnlyAdded"
    case stickersChannelReactions = "GRVMgram.Chats.Stickers.ChannelReactions"
    case stickersGroupReactions = "GRVMgram.Chats.Stickers.GroupReactions"
    case stickersRecent = "GRVMgram.Chats.Stickers.Recent"
    case channelsHeader = "GRVMgram.Chats.Channels.Header"
    case channelsQuickAdmin = "GRVMgram.Chats.Channels.QuickAdmin"
    case channelsMessageShot = "GRVMgram.Chats.Channels.MessageShot"
    case channelsBottomButton = "GRVMgram.Chats.Channels.BottomButton"
    case channelsBottomHide = "GRVMgram.Chats.Channels.BottomButton.Hide"
    case channelsBottomMute = "GRVMgram.Chats.Channels.BottomButton.Mute"
    case channelsBottomDiscuss = "GRVMgram.Chats.Channels.BottomButton.Discuss"
    case messagesHeader = "GRVMgram.Chats.Messages.Header"
    case deletedMark = "GRVMgram.Chat.DeletedMark"
    case deletedMarkPrompt = "GRVMgram.Chat.DeletedMark.Prompt"
    case deletedMarkDefault = "GRVMgram.Chat.DeletedMark.Default"
    case editedMark = "GRVMgram.Chat.EditedMark"
    case editedMarkPrompt = "GRVMgram.Chat.EditedMark.Prompt"
    case editedMarkDefault = "GRVMgram.Chat.EditedMark.Default"
    case messagesIcons = "GRVMgram.Chats.Messages.Icons"
    case messagesFastShare = "GRVMgram.Chats.Messages.FastShare"
    case messagesColoredReplies = "GRVMgram.Chats.Messages.ColoredReplies"
    case messagesWidth = "GRVMgram.Chats.Messages.Width"
    case messagesTranslucent = "GRVMgram.Chats.Messages.Translucent"
    case contextHeader = "GRVMgram.Chats.Context.Header"
    case contextReactions = "GRVMgram.Chats.Context.Reactions"
    case contextViews = "GRVMgram.Chats.Context.Views"
    case contextHide = "GRVMgram.Chats.Context.Hide"
    case contextUserMessages = "GRVMgram.Chats.Context.UserMessages"
    case contextDetails = "GRVMgram.Chats.Context.Details"
    case contextRepeat = "GRVMgram.Chats.Context.Repeat"
    case contextAddFilter = "GRVMgram.Chats.Context.AddFilter"
    case fieldHeader = "GRVMgram.Chats.Field.Header"
    case fieldAttach = "GRVMgram.Chats.Field.Attach"
    case fieldCommands = "GRVMgram.Chats.Field.Commands"
    case fieldTtl = "GRVMgram.Chats.Field.TTL"
    case fieldEmoji = "GRVMgram.Chats.Field.Emoji"
    case fieldVoice = "GRVMgram.Chats.Field.Voice"
    case fieldGift = "GRVMgram.Chats.Field.Gift"
    case fieldAi = "GRVMgram.Chats.Field.AI"

    case deletedTitle = "GRVMgram.Deleted.Title"
    case deletedEmpty = "GRVMgram.Deleted.Empty"
    case deletedRecent = "GRVMgram.Deleted.Recent"
    case deletedMessageEmpty = "GRVMgram.Deleted.MessageEmpty"
    case deletedMedia = "GRVMgram.Deleted.Media"
    case deletedMediaWithText = "GRVMgram.Deleted.MediaWithText"
    case deletedAuthor = "GRVMgram.Deleted.Author"
    case deletedAttachment = "GRVMgram.Deleted.Attachment"
    case deletedMediaUnavailable = "GRVMgram.Deleted.MediaUnavailable"
    case deletedClearTitle = "GRVMgram.Deleted.Clear.Title"
    case deletedClearText = "GRVMgram.Deleted.Clear.Text"
    case deletedClearAction = "GRVMgram.Deleted.Clear.Action"
    case historyTitle = "GRVMgram.History.Title"
    case historyEmpty = "GRVMgram.History.Empty"
    case historyRecent = "GRVMgram.History.Recent"
    case historyRevision = "GRVMgram.History.Revision"
    case historyAction = "GRVMgram.History.Action"

    case chatMenuTitle = "GRVMgram.ChatMenu.Title"
    case chatMenuViewDeleted = "GRVMgram.ChatMenu.ViewDeleted"
    case chatMenuClearDeleted = "GRVMgram.ChatMenu.ClearDeleted"
    case menuLocalHide = "GRVMgram.Menu.LocalHide"
    case menuUserMessages = "GRVMgram.Menu.UserMessages"
    case menuDetails = "GRVMgram.Menu.Details"
    case menuRepeat = "GRVMgram.Menu.Repeat"
    case menuAddFilter = "GRVMgram.Menu.AddFilter"
    case menuViewFilters = "GRVMgram.Menu.ViewFilters"
    case menuDeleteOwn = "GRVMgram.Menu.DeleteOwn"
    case menuReadMessage = "GRVMgram.Menu.ReadMessage"
    case menuReadAllLocal = "GRVMgram.Menu.ReadAllLocal"
    case menuReadAllServer = "GRVMgram.Menu.ReadAllServer"
    case menuBurn = "GRVMgram.Menu.Burn"
    case menuSendAsSticker = "GRVMgram.Menu.SendAsSticker"
    case menuCopyId = "GRVMgram.Menu.CopyID"
    case menuCopyCallback = "GRVMgram.Menu.CopyCallback"
    case menuJumpBeginning = "GRVMgram.Menu.JumpBeginning"
    case menuOpenProfileId = "GRVMgram.Menu.OpenProfileID"

    case confirmSendSticker = "GRVMgram.Confirm.SendSticker"
    case confirmSendGif = "GRVMgram.Confirm.SendGIF"
    case confirmSendVoice = "GRVMgram.Confirm.SendVoice"
    case storyGhostTitle = "GRVMgram.StoryGhost.Title"
    case storyGhostText = "GRVMgram.StoryGhost.Text"
    case storyGhostEnable = "GRVMgram.StoryGhost.Enable"
    case storyGhostOpen = "GRVMgram.StoryGhost.Open"

    case messageShotTitle = "GRVMgram.MessageShot.Title"
    case messageShotDate = "GRVMgram.MessageShot.Date"
    case messageShotHeader = "GRVMgram.MessageShot.Header"
    case messageShotDecorations = "GRVMgram.MessageShot.Decorations"
    case messageShotSpoilers = "GRVMgram.MessageShot.Spoilers"
    case messageShotTheme = "GRVMgram.MessageShot.Theme"
    case messageShotReplies = "GRVMgram.MessageShot.Replies"
    case messageShotCopy = "GRVMgram.MessageShot.Copy"
    case messageShotSave = "GRVMgram.MessageShot.Save"

    case otherTitle = "GRVMgram.Other.Title"
    case otherHeader = "GRVMgram.Other.Header"
    case crashTitle = "GRVMgram.Crash.Title"
    case crashInfo = "GRVMgram.Crash.Info"
    case crashExport = "GRVMgram.Crash.Export"
    case crashNoReports = "GRVMgram.Crash.NoReports"
    case resetTitle = "GRVMgram.Reset.Title"
    case resetText = "GRVMgram.Reset.Text"
    case resetAction = "GRVMgram.Reset.Action"
    case streamerTitle = "GRVMgram.Streamer.Title"
    case streamerInfo = "GRVMgram.Streamer.Info"
}

public struct GRVMgramStrings {
    public let languageCode: String
    private let values: [String: String]
    private let englishValues: [String: String]

    public init(_ presentationStrings: PresentationStrings) {
        let baseCode = presentationStrings.baseLanguageCode.lowercased()
        self.languageCode = baseCode == "ru" || baseCode.hasPrefix("ru-") ? "ru" : "en"
        self.englishValues = Self.english
        self.values = self.languageCode == "ru" ? Self.russian : Self.english
    }

    public subscript(_ key: GRVMgramStringKey) -> String {
        return self.values[key.rawValue]
            ?? self.englishValues[key.rawValue]
            ?? key.rawValue
    }

    public func format(_ key: GRVMgramStringKey, _ arguments: CVarArg...) -> String {
        return String(
            format: self[key],
            locale: Locale(identifier: self.languageCode),
            arguments: arguments
        )
    }

    private static let english = Self.load(languageCode: "en")
    private static let russian = Self.load(languageCode: "ru")

    private static func load(languageCode: String) -> [String: String] {
        guard let path = getAppBundle().path(
            forResource: "GRVMgram",
            ofType: "strings",
            inDirectory: nil,
            forLocalization: languageCode
        ), let dictionary = NSDictionary(contentsOfFile: path) as? [String: String] else {
            return [:]
        }
        return dictionary
    }
}
```

- [ ] **Step 4: Create complete English and Russian tables**

Create both `.strings` files with every enum raw value exactly once. Use these translations for all visible concepts; preserve `%d` and `%@` tokens in the same order:

| English | Russian |
|---|---|
| GRVMgram Settings | Настройки GRVMgram |
| Filters | Фильтры |
| General | Основные |
| Appearance | Оформление |
| Chats | Чаты |
| Other | Другое |
| Deleted Messages | Удалённые сообщения |
| Edit History | История правок |
| Default | По умолчанию |
| Off | Выключено |
| Hidden | Скрыто |
| Shown | Показано |
| With Modifier | С модификатором |
| Never | Никогда |
| In Ghost Mode | В гост-режиме |
| Always | Всегда |
| Search | Поиск |
| Clear | Очистить |
| Export | Экспортировать |
| Import | Импортировать |
| Ghost Mode | Гост-режим |
| Don't Send Read Receipts | Не отправлять отчёты о прочтении |
| Don't Send Story Views | Не отправлять просмотры историй |
| Don't Send Online Status | Не отправлять статус «в сети» |
| Don't Send Typing Status | Не отправлять статус набора текста |
| Don't Send Upload Progress | Не отправлять прогресс загрузки |
| Go Offline Automatically | Автоматически уходить не в сеть |
| Mark Read on Action | Читать при действии |
| Mark messages read after sending, reacting, or voting. | Отмечать сообщения прочитанными после отправки, реакции или голосования. |
| Suggest Ghost Mode for Stories | Предлагать гост-режим для историй |
| Ask before opening a story when private viewing is disabled. | Спрашивать перед открытием истории, если приватный просмотр выключен. |
| Use Scheduled Messages | Использовать отложенную отправку |
| Schedule outgoing messages to avoid showing online presence. | Откладывать исходящие сообщения, чтобы не показывать статус «в сети». |
| Send Without Sound | Отправлять без звука |
| Choose when outgoing messages are sent silently. | Выберите, когда исходящие сообщения отправляются без звука. |
| %d/5 enabled | Включено: %d/5 |
| Spy Mode | Режим сохранения |
| Save Deleted Messages | Сохранять удалённые сообщения |
| Save Edit History | Сохранять историю правок |
| Save in Bot Chats | Сохранять в чатах с ботами |
| Local Telegram Premium | Локальный Telegram Premium |
| Disable Ads | Отключить рекламу |
| Message Filters | Фильтры сообщений |
| Enable Filters | Включить фильтры |
| Enable Filters in Chats | Применять фильтры в чатах |
| Hide from Blocked Users | Скрывать сообщения заблокированных пользователей |
| Filter Patterns (Regex) | Шаблоны фильтров (Regex) |
| Add Filter | Добавить фильтр |
| Add Filter Pattern (Regex) | Добавить шаблон фильтра (Regex) |
| Edit Filter Pattern (Regex) | Изменить шаблон фильтра (Regex) |
| Reversed Filters (hide all except matches) | Обратные фильтры (скрывать всё, кроме совпадений) |
| Add Reversed Filter | Добавить обратный фильтр |
| Global Filters | Общие фильтры |
| Case Sensitive | Учитывать регистр |
| Message Type | Тип сообщения |
| Button Text | Текст кнопки |
| Select Chat | Выбрать чат |
| Show Filtered | Показать отфильтрованные |
| Hide Filtered | Скрыть отфильтрованные |
| Shadow Ban | Теневой бан |
| Shadow Banned IDs | ID в теневом бане |
| Add ID | Добавить ID |
| Add Peer ID | Добавить Peer ID |
| Edit Peer ID | Изменить Peer ID |
| Message Translation | Перевод сообщений |
| Translation Provider | Сервис перевода |
| Telegram | Telegram |
| Google | Google |
| Yandex | Яндекс |
| Native | Системный |
| Hide Stories | Скрыть истории |
| Disable Similar Channels | Отключить похожие каналы |
| Disable Notification Delay | Отключить задержку уведомлений |
| Show Seconds in Messages | Показывать секунды в сообщениях |
| Show Peer ID | Показывать Peer ID |
| Filter Zalgo | Фильтровать Zalgo |
| Improve Link Previews | Улучшать предпросмотр ссылок |
| Disable Open Link Warning | Отключить предупреждение о ссылках |
| Webview | Веб-приложения |
| Spoof Platform as Android | Представляться Android |
| Increase Height | Увеличить высоту |
| Increase Width | Увеличить ширину |
| Confirmations | Подтверждения |
| For Stickers | Для стикеров |
| For GIFs | Для GIF |
| For Voice Messages | Для голосовых сообщений |
| App Icon | Иконка приложения |
| Black | Чёрная |
| Classic Black | Классическая чёрная |
| Filled Black | Залитая чёрная |
| Blue | Синяя |
| Classic Blue | Классическая синяя |
| Filled Blue | Залитая синяя |
| Filled White | Залитая белая |
| Gradient Pink | Розовый градиент |
| Gradient Green | Зелёный градиент |
| Premium | Premium |
| Premium Black | Чёрная Premium |
| Premium Turbo | Premium Turbo |
| Hide Notification Badge | Скрыть значок уведомлений |
| Hide Notification Counters | Скрыть счётчики уведомлений |
| MD3 Style Switches | Переключатели в стиле MD3 |
| Remove Message Tail | Убрать хвост сообщения |
| Disable Custom Backgrounds | Отключить пользовательские фоны |
| Code Font | Шрифт кода |
| Avatar Corners | Закругление аватаров |
| Message Bubble Radius | Радиус сообщений |
| Single Corner Radius | Единый радиус углов |
| Hide Premium Statuses | Скрыть Premium-статусы |
| Folders | Папки |
| Hide Folder Counters | Скрыть счётчики папок |
| Hide All Chats | Скрыть «Все чаты» |
| Stickers & Emoji | Стикеры и эмодзи |
| Show Only Added Stickers | Показывать только добавленные стикеры |
| Show Channel Reactions | Показывать реакции в каналах |
| Show Group Reactions | Показывать реакции в группах |
| Recent Stickers Count | Количество недавних стикеров |
| Groups & Channels | Группы и каналы |
| Quick Admin Shortcuts | Быстрые действия администратора |
| Message Shot | Снимок сообщений |
| Channel Bottom Button | Нижняя кнопка канала |
| Mute/Unmute | Включить/выключить звук |
| Discuss | Обсудить |
| Messages | Сообщения |
| Deleted Mark | Метка удаления |
| Enter deleted-message mark | Введите метку удалённого сообщения |
| Edited Mark | Метка изменения |
| Enter edited-message mark | Введите метку изменённого сообщения |
| Replace Marks with Icons | Заменять метки значками |
| Hide Fast Share Button | Скрыть кнопку быстрой пересылки |
| Disable Colored Replies | Отключить цветные ответы |
| Message Width | Ширина сообщения |
| Translucent Deleted Messages | Полупрозрачные удалённые сообщения |
| Context Menu Elements | Элементы контекстного меню |
| Reactions Panel | Панель реакций |
| Views Panel | Панель просмотров |
| Hide Message | Скрыть сообщение |
| User's Messages | Сообщения пользователя |
| Message Details | Сведения о сообщении |
| Repeat Message | Повторить сообщение |
| Add Filter | Добавить фильтр |
| Message Field Elements | Элементы поля сообщения |
| Attachment | Вложения |
| Commands | Команды |
| Emoji & Stickers | Эмодзи и стикеры |
| Voice Recording | Запись голоса |
| Gift | Подарок |
| AI Editor | AI-редактор |
| Message Shot | Снимок сообщений |
| Date | Дата |
| Header | Заголовок |
| Decorations | Оформление |
| Reveal Spoilers | Показать спойлеры |
| Theme | Тема |
| Colorful Replies | Цветные ответы |
| Copy | Копировать |
| Save | Сохранить |
| No deleted messages have been saved yet. | Сохранённых удалённых сообщений пока нет. |
| Recent Deleted Messages | Недавно удалённые сообщения |
| [empty] | [пусто] |
| [%@] | [%@] |
| [%@] %@ | [%@] %@ |
| %1$@: %2$@ | %1$@: %2$@ |
| Attachment available | Вложение доступно |
| Media was not downloaded before deletion. | Медиа не было загружено до удаления. |
| Clear Deleted Messages? | Очистить удалённые сообщения? |
| Messages and persistent media will be removed from this chat. | Сообщения и сохранённые медиа будут удалены из этого чата. |
| No edit history has been saved yet. | История правок пока пуста. |
| Recent Edited Messages | Недавние изменения сообщений |
| Version %d | Версия %d |
| History | История |
| GRVMgram | GRVMgram |
| View Deleted | Посмотреть удалённые |
| Clear Deleted | Очистить удалённые |
| Hide Locally | Скрыть локально |
| User Messages | Сообщения пользователя |
| Details | Сведения |
| Repeat | Повторить |
| View Filters | Посмотреть фильтры |
| Delete Own Messages | Удалить свои сообщения |
| Read Message | Прочитать сообщение |
| Read All Locally | Прочитать всё локально |
| Read All on Server | Прочитать всё на сервере |
| Burn | Сжечь |
| Send as Sticker | Отправить как стикер |
| Copy ID | Копировать ID |
| Copy Callback Data | Копировать callback data |
| Jump to Beginning | Перейти в начало |
| Open Profile by ID | Открыть профиль по ID |
| Send sticker? | Отправить стикер? |
| Send GIF? | Отправить GIF? |
| Send voice message? | Отправить голосовое сообщение? |
| Private Story Viewing | Приватный просмотр историй |
| Enable Ghost Mode before opening this story? | Включить гост-режим перед открытием этой истории? |
| Enable Ghost Mode | Включить гост-режим |
| Open Normally | Открыть обычно |
| Crash Reporting | Отчёты о сбоях |
| Offer to export a local crash report after an unexpected termination. Nothing is uploaded automatically. | Предлагать экспортировать локальный отчёт после неожиданного завершения. Ничего не отправляется автоматически. |
| Export Crash Report | Экспортировать отчёт о сбое |
| No crash reports found. | Отчёты о сбоях не найдены. |
| Reset Settings | Сбросить настройки |
| Reset all GRVMgram settings? | Сбросить все настройки GRVMgram? |
| This does not delete your Telegram account or chats. | Аккаунт Telegram и чаты удалены не будут. |
| Streamer Privacy | Защита трансляции |
| Cover private content while the screen is being captured. | Скрывать личные данные во время записи или трансляции экрана. |

Use `Telegram` and `Google` unchanged, `Yandex` / `Яндекс`, and `Native` / `Системный`. Use `🧹` for `GRVMgram.Chat.DeletedMark.Default` and `edited` / `изменено` for `GRVMgram.Chat.EditedMark.Default`.

- [ ] **Step 5: Package the resources in the application**

Modify `Telegram/BUILD:251-258` to:

```python
filegroup(
    name = "AppStringResources",
    srcs = [
        "Telegram-iOS/en.lproj/Localizable.strings",
        "Telegram-iOS/en.lproj/GRVMgram.strings",
        "Telegram-iOS/ru.lproj/GRVMgram.strings",
    ] + [
        "{}.lproj/Localizable.strings".format(language) for language in empty_languages
    ],
)
```

- [ ] **Step 6: Run localization contract tests and verify GREEN**

From the repository root:

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
python build-system/Make/ValidateGRVMgram.py source
```

At this intermediate point, unit tests must pass. `source` is expected to remain non-zero and list existing raw UI/AyuGram/workflow findings; save that output as the RED list for Tasks 3-6.

- [ ] **Step 7: Commit localization infrastructure without staging the Ghost file**

```powershell
git add -- Telegram/BUILD Telegram/Telegram-iOS/en.lproj/GRVMgram.strings Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift Tests/GRVMgramValidation/test_validate_grvmgram.py
git diff --cached --check
git commit -m "feat: add GRVMgram English and Russian resources"
```

Expected: commit contains only localization resources, loader, BUILD resource registration, and the localization test.

---

### Task 3: Remove Project/Donation UI and Rebrand Main Settings

**Files:**
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramMainController.swift:14-165`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift:14-161`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift:1038`

**Interfaces:**
- Consumes: `GRVMgramStrings` and `GRVMgramStringKey` from Task 2.
- Preserves: public entry points `ayuGramMainController(context:)` and `ayuGramOtherController(context:)`.
- Removes: all runtime actions that open or copy original-project links/donation addresses.
- Preserves: internal `AyuGramMainEntry`, `AyuGramSettings`, settings keys, and database identifiers.

- [ ] **Step 1: Add a failing repository branding test**

Add to `BrandingTests`:

```python
    def test_repository_has_no_public_ayugram_branding(self) -> None:
        VALIDATOR.validate_public_branding(REPOSITORY_ROOT)
```

- [ ] **Step 2: Run the branding test and verify RED**

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
```

Expected: FAIL listing `AyuGramMainController.swift`, `AyuGramOtherController.swift`, the app-icon log, Telegram URLs, Boosty, and crypto addresses.

- [ ] **Step 3: Delete the Main About/Links structure and localize the functional list**

In `AyuGramMainController.swift`:

- `AyuGramMainSection` contains only `case categories`.
- Delete entry cases `header`, `linkChannel`, `linkChat`, and `linkDocs`.
- Delete the matching `section`, `stableId`, and `item` switch arms.
- Delete the version/fork header and all three link appends.
- Keep internal case `categoryAyuGram`, but render `strings[.mainCore]`.
- Render every remaining title through `GRVMgramStrings(presentationData.strings)`.
- Set controller title to `strings[.settingsTitle]`.

The resulting entry builder must append exactly these eight rows, in this order:

```swift
private func ayuGramMainEntries(
    presentationData: PresentationData
) -> [AyuGramMainEntry] {
    return [
        .categoryAyuGram(presentationData.theme),
        .categoryFilters(presentationData.theme),
        .categoryGeneral(presentationData.theme),
        .categoryAppearance(presentationData.theme),
        .categoryChats(presentationData.theme),
        .categoryOther(presentationData.theme),
        .spyHistory(presentationData.theme),
        .editHistory(presentationData.theme),
    ]
}
```

- [ ] **Step 4: Delete donations and dead link association from Other**

In `AyuGramOtherController.swift`:

- Remove `UIKit` if no remaining type requires it.
- Remove `context`, `openURL`, and `copyToClipboard` from `AyuGramOtherArguments`.
- Remove `AyuGramOtherSection.support`.
- Remove cases `supportHeader`, `boosty`, `ton`, `bitcoin`, `ethereum`, `solana`, `tron`, `supportInfo`, and `associateLinks`.
- Leave the Codable/model field `associateLinks` unchanged for migration compatibility.
- Keep only `otherHeader`, `crashReporting`, `crashReportingInfo`, and `resetSettings` rows.
- Render all text with `GRVMgramStrings`.
- Preserve the reset closure supplied by the parity task, including its confirmation alert.

The final entries function must be:

```swift
private func ayuGramOtherEntries(
    settings: AyuGramSettings,
    presentationData: PresentationData
) -> [AyuGramOtherEntry] {
    return [
        .otherHeader(presentationData.theme),
        .crashReporting(presentationData.theme, settings.crashReportingEnabled),
        .crashReportingInfo(presentationData.theme),
        .resetSettings(presentationData.theme),
    ]
}
```

- [ ] **Step 5: Rebrand the app-icon log exported in diagnostics**

Apply this exact replacement:

```swift
Logger.shared.log(
    "App \(self.episodeId)",
    "failed to apply GRVMgram app icon \(String(describing: desiredIconName)) with error \(error.localizedDescription)"
)
```

- [ ] **Step 6: Run branding tests and targeted forbidden-token scan**

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
rg -n -i "t\.me/ayugram|docs\.ayugram|boosty\.to/ayugram|@ayugram|github\.com/AyuGram|crowdin\.com/project/ayugram|UQA4i8U8|bc1qdk|0x405589|8ZHQp|TRpbaj" submodules/AyuGramSettingsUI submodules/AyuGramLib submodules/TelegramUI
```

Expected: unit tests pass; `rg` prints no matches.

- [ ] **Step 7: Commit the removed project UI and public brand changes**

```powershell
git add -- submodules/AyuGramSettingsUI/Sources/AyuGramMainController.swift submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift submodules/TelegramUI/Sources/AppDelegate.swift Tests/GRVMgramValidation/test_validate_grvmgram.py
git diff --cached --check
git commit -m "feat: remove AyuGram project links and branding"
```

---

### Task 4: Localize Every GRVMgram Settings Screen

**Files:**
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramEditedMessagesController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramShadowBanController.swift`
- Modify: any GRVMgram-specific controllers created by earlier parity tasks under `submodules/AyuGramSettingsUI/Sources/`.

**Interfaces:**
- Consumes: `ItemListPresentationData.strings` or `PresentationData.strings`.
- Consumes: `GRVMgramStrings` from Task 2.
- Preserves: stock Telegram strings such as `Common_Back`, `Common_Cancel`, `Common_OK`, `Common_Done`.
- Produces: no user-facing alphabetic Swift literal in `submodules/AyuGramSettingsUI/Sources/*.swift` except technical icon IDs and font names allowlisted by the validator.

- [ ] **Step 1: Run the source validator and capture the Settings UI RED list**

```powershell
python build-system/Make/ValidateGRVMgram.py source
```

Expected: non-zero exit with `hard-coded GRVMgram Settings UI text` and exact file/line/literal entries.

- [ ] **Step 2: Localize Core and enforce current Ghost semantics**

At the start of every `item(...)` implementation, create:

```swift
let strings = GRVMgramStrings(presentationData.strings)
```

Replace Core literals using the matching `.ghost*`, `.spy*`, and `.core*` keys. Use:

```swift
strings.format(.ghostActiveCount, Int32(settings.ghostModeActiveCount))
```

for the active-count label. Do not recreate removed Desktop Drawer settings. Do not alter Ghost logic while localizing it.

- [ ] **Step 3: Localize Filters and Shadow Ban editors**

Replace all headers, row titles, empty/action labels, prompt titles, import/export/clear labels, type/button labels, and case-sensitive labels with `.filters*` and `.shadow*` keys. Keep regex values, peer IDs, and imported JSON content unmodified.

For prompt selection, use explicit localized branches:

```swift
let strings = GRVMgramStrings(
    context.sharedContext.currentPresentationData.with { $0 }.strings
)
let title = index == nil ? strings[.filtersAddPrompt] : strings[.filtersEditPrompt]
```

- [ ] **Step 4: Localize General and Appearance**

Map provider integers to localized values, not raw literals:

```swift
let providerTitles = [
    strings[.translationTelegram],
    strings[.translationGoogle],
    strings[.translationYandex],
    strings[.translationNative],
]
```

Map peer-ID mode to `.commonOff`, `.peerIdApi`, `.peerIdBotApi`.

Map icon IDs to localized keys while preserving the stored ID:

```swift
let appIconTitles: [String: GRVMgramStringKey] = [
    "default": .commonDefault,
    "Black": .appIconBlack,
    "BlackClassic": .appIconBlackClassic,
    "BlackFilled": .appIconBlackFilled,
    "Blue": .appIconBlue,
    "BlueClassic": .appIconBlueClassic,
    "BlueFilled": .appIconBlueFilled,
    "WhiteFilled": .appIconWhiteFilled,
    "New1": .appIconNew1,
    "New2": .appIconNew2,
    "Premium": .appIconPremium,
    "PremiumBlack": .appIconPremiumBlack,
    "PremiumTurbo": .appIconPremiumTurbo,
]
let visibleTitle = appIconTitles[settings.selectedAppIcon].map { strings[$0] }
    ?? settings.selectedAppIcon
```

Delete Ghost/Streamer Drawer rows because iOS has no Desktop Drawer. Keep model fields for decode compatibility.

- [ ] **Step 5: Localize Chats, marks, options, and Message Shot**

Replace each alphabetic literal in `AyuGramChatsController.swift` with a `.chats*`, `.messages*`, `.context*`, `.field*`, or `.messageShot*` key.

Use these option arrays:

```swift
let channelButtonTitles = [
    strings[.channelsBottomHide],
    strings[.channelsBottomMute],
    strings[.channelsBottomDiscuss],
]
let contextVisibilityTitles = [
    strings[.commonHidden],
    strings[.commonShown],
    strings[.commonWithModifier],
]
```

Do not cycle deleted/edited marks through presets. The parity task's free-text editors must use `.deletedMarkPrompt` and `.editedMarkPrompt`; an empty edited mark renders `.editedMarkDefault`.

- [ ] **Step 6: Localize deleted archives and per-message history**

Use format keys instead of concatenated display text:

```swift
let body: String
if message.text.isEmpty && message.mediaDescription.isEmpty {
    body = strings[.deletedMessageEmpty]
} else if message.text.isEmpty {
    body = strings.format(.deletedMedia, message.mediaDescription)
} else if !message.mediaDescription.isEmpty {
    body = strings.format(
        .deletedMediaWithText,
        message.mediaDescription,
        message.text
    )
} else {
    body = message.text
}
let display = strings.format(.deletedAuthor, who, body)
```

Use `.historyRevision` for revision numbering, `.deletedMediaUnavailable` for missing backups, and `.deletedClear*` for cleanup confirmation. Per-message History must retain its exact message filter; localization must not change its query.

- [ ] **Step 7: Run the Settings UI literal validator**

```powershell
python build-system/Make/ValidateGRVMgram.py source
```

Expected: Settings hard-coded-literal failures are gone. Metadata/workflow or cross-module failures may remain until Tasks 5-6.

- [ ] **Step 8: Commit all localized settings screens**

```powershell
git add -- submodules/AyuGramSettingsUI/Sources Telegram/Telegram-iOS/en.lproj/GRVMgram.strings Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift
git diff --cached --check
git commit -m "feat: localize GRVMgram settings in English and Russian"
```

Expected: no TelegramCore Ghost file is staged.

---

### Task 5: Localize Cross-Module Actions and Complete Public Metadata

**Files:**
- Modify: `submodules/TelegramUI/Sources/ChatController.swift:2249-2256,2419-2427`
- Modify: `submodules/TelegramUI/Sources/Chat/ChatControllerMediaRecording.swift:690-699`
- Modify: `submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryContainerScreen.swift`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoSettingsItems.swift:254-256`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- Modify: chat-menu/history/Message Shot/crash UI files created by earlier tasks.
- Modify: `Telegram/BUILD`
- Modify: `Telegram/Telegram-iOS/Config-Fork.xcconfig`
- Modify: `Telegram/Telegram-iOS/ar.lproj/InfoPlist.strings`
- Modify: `Telegram/Telegram-iOS/ko.lproj/InfoPlist.strings`
- Modify: both `GRVMgram.strings` files and `GRVMgramStringKey` if a final parity screen consumes an already-defined key not yet referenced.

**Interfaces:**
- Consumes: `GRVMgramStrings(currentPresentationData.strings)`.
- Preserves: stock Telegram alert buttons from `PresentationStrings`.
- Produces: main and extension `CFBundleDisplayName`/`CFBundleName` values branded `GRVMgram`.
- Preserves: internal framework bundle names `TelegramApi`, `TelegramCore`, and `TelegramUI`.

- [ ] **Step 1: Add failing repository metadata and final-source tests**

Add to `BrandingTests`:

```python
    def test_repository_metadata_is_branded(self) -> None:
        VALIDATOR.validate_metadata(REPOSITORY_ROOT)
```

Run:

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
```

Expected: FAIL because extension `CFBundleName` values remain `Telegram`, theme description remains `Telegram iOS Color Theme File`, fork xcconfig remains `Telegram Fork`, and Arabic/Korean display-name overrides remain.

- [ ] **Step 2: Localize send-confirmation and story alerts**

Use current presentation data and preserve stock Cancel/OK buttons:

```swift
let grvmStrings = GRVMgramStrings(strongSelf.presentationData.strings)
let alertController = textAlertController(
    context: strongSelf.context,
    title: nil,
    text: grvmStrings[.confirmSendSticker],
    actions: [
        TextAlertAction(
            type: .genericAction,
            title: strongSelf.presentationData.strings.Common_Cancel,
            action: {}
        ),
        TextAlertAction(
            type: .defaultAction,
            title: strongSelf.presentationData.strings.Common_OK,
            action: confirmSend
        ),
    ]
)
```

Apply `.confirmSendGif` and `.confirmSendVoice` in their respective flows.

The Story Ghost prompt implemented earlier must use `.storyGhostTitle`, `.storyGhostText`, `.storyGhostEnable`, and `.storyGhostOpen`, and it must still appear before the view operation.

- [ ] **Step 3: Localize settings row, chat menu, History, and parity actions**

Replace the raw settings label with:

```swift
let grvmStrings = GRVMgramStrings(presentationData.strings)
items[.advanced]!.append(
    PeerInfoScreenDisclosureItem(
        id: 7,
        text: grvmStrings[.settingsTitle],
        icon: PresentationResourcesSettings.appearance,
        action: {
            interaction.openSettings(.ayuGramSettings)
        }
    )
)
```

Use `.chatMenuTitle`, `.chatMenuViewDeleted`, `.chatMenuClearDeleted`, `.historyAction`, and the exact `.menu*` keys for GRVMgram context/chat actions. Do not replace stock Telegram menu text.

- [ ] **Step 4: Rebrand app and extension metadata without renaming internal targets**

In `Telegram/BUILD`:

- Keep `AppNameInfoPlist` and main `TelegramInfoPlist` values `GRVMgram`.
- Change exact `<string>Telegram</string>` values for Share, Notification Content, Widget, Siri Intents, Broadcast Upload, and Notification Service to `<string>GRVMgram</string>`.
- Change `Telegram iOS Color Theme File` to `GRVMgram Color Theme File`.
- Leave `TelegramApi`, `TelegramCore`, `TelegramUI`, bundle identifiers, URL schemes, and target names unchanged.

Change only the existing `APP_NAME` assignment in `Telegram/Telegram-iOS/Config-Fork.xcconfig`:

```xcconfig
APP_NAME=GRVMgram
```

Preserve `APP_BUNDLE_ID`, `APP_SPECIFIC_URL_SCHEME`, `GLOBAL_CONSTANTS`, and both compiler-definition lines verbatim.

Delete only the `CFBundleDisplayName` assignment from Arabic and Korean `InfoPlist.strings`; leave their permission descriptions intact.

- [ ] **Step 5: Run metadata, localization, branding, and diff checks**

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
python build-system/Make/ValidateGRVMgram.py source
git diff --check
```

Expected before Task 6: unit tests and metadata/branding/localization checks pass; `source` may fail only on the not-yet-updated workflow contract.

- [ ] **Step 6: Commit cross-module localization and public metadata**

```powershell
git add -- Telegram/BUILD Telegram/Telegram-iOS/Config-Fork.xcconfig Telegram/Telegram-iOS/ar.lproj/InfoPlist.strings Telegram/Telegram-iOS/ko.lproj/InfoPlist.strings submodules/TelegramUI Telegram/Telegram-iOS/en.lproj/GRVMgram.strings Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift Tests/GRVMgramValidation/test_validate_grvmgram.py
git diff --cached --check
git commit -m "feat: complete GRVMgram public localization and branding"
```

Before committing, inspect `git diff --cached --name-only` and unstage any unrelated TelegramUI file not changed for localization/branding.

---

### Task 6: Make GitHub Actions Produce and Validate `GRVMgram.ipa`

**Files:**
- Modify: `.github/workflows/build.yml:13-157`
- Modify: `Tests/GRVMgramValidation/test_validate_grvmgram.py`

**Interfaces:**
- Consumes: `python3 build-system/Make/ValidateGRVMgram.py source` before the expensive build.
- Consumes: internal Bazel artifact `bazel-bin/Telegram/Telegram.ipa` or the existing `bazel-out` fallback.
- Produces: `artifacts/GRVMgram.ipa`.
- Produces: GitHub artifact `GRVMgram-ipa`.
- Produces: a non-zero job result for missing, empty, malformed, incorrectly branded, or incompletely localized IPA.
- Preserves: always-uploaded `build-log` artifact.

- [ ] **Step 1: Add a failing repository workflow-contract test**

Add to `BrandingTests`:

```python
    def test_repository_workflow_validates_grvmgram_ipa(self) -> None:
        VALIDATOR.validate_workflow(REPOSITORY_ROOT)
```

- [ ] **Step 2: Run the workflow test and verify RED**

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
```

Expected: FAIL listing the missing source-validation step, `GRVMgram.ipa` copy, IPA-validation step, `GRVMgram-ipa`, and `if-no-files-found: error`.

- [ ] **Step 3: Add the cheap source gate immediately after checkout**

Insert after `actions/checkout@v4`:

```yaml
      - name: Validate GRVMgram sources
        run: |
          python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v
          python3 build-system/Make/ValidateGRVMgram.py source
```

This step must precede `Fetch submodules by exact commit` so source mistakes fail before the expensive setup/build.

- [ ] **Step 4: Replace Collect IPA with a hard-failing external artifact copy**

Use this complete step:

```yaml
      - name: Collect IPA
        if: success()
        run: |
          set -euo pipefail
          SOURCE_DIR=/Users/Shared/telegram-ios
          cd "$SOURCE_DIR"
          IPA="bazel-bin/Telegram/Telegram.ipa"
          if [ ! -e "$IPA" ]; then
            IPA="$(ls -1 bazel-out/*/bin/Telegram/Telegram.ipa 2>/dev/null | head -1 || true)"
          fi
          if [ -z "$IPA" ] || [ ! -e "$IPA" ]; then
            echo "ERROR: Telegram.ipa not found. Contents of bazel-bin/Telegram:"
            ls -la bazel-bin/Telegram/ 2>/dev/null | head -60 || true
            exit 1
          fi
          mkdir -p "$GITHUB_WORKSPACE/artifacts"
          cp -L "$IPA" "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"
          test -s "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"
          ls -lh "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"
```

- [ ] **Step 5: Validate and upload only the final IPA file**

Replace the old upload block with:

```yaml
      - name: Validate GRVMgram IPA
        if: success()
        run: python3 build-system/Make/ValidateGRVMgram.py ipa artifacts/GRVMgram.ipa

      - name: Upload IPA
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: GRVMgram-ipa
          path: artifacts/GRVMgram.ipa
          if-no-files-found: error
```

- [ ] **Step 6: Run the complete Windows gate**

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
python build-system/Make/ValidateGRVMgram.py source
python -m py_compile build-system/Make/ValidateGRVMgram.py
git diff --check
```

Expected: all tests report `OK`; source validator prints `GRVMgram source validation passed`; remaining commands exit 0 without output.

- [ ] **Step 7: Commit the final workflow contract**

```powershell
git add -- .github/workflows/build.yml Tests/GRVMgramValidation/test_validate_grvmgram.py
git diff --cached --check
git commit -m "ci: validate and publish GRVMgram IPA"
```

---

### Task 7: Final Local Audit, One Master Push, and Persistent CI Monitoring

**Files:**
- Verify only; create no tracked source file.
- Download runtime artifacts under ignored `build/ci/<run-id>/`.

**Interfaces:**
- Consumes: clean committed feature/localization branch plus the intentional Ghost commit created by the main implementation plan.
- Consumes: GitHub workflow `build.yml` on `master`.
- Produces: successful run ID, run URL, `GRVMgram-ipa`, local `GRVMgram.ipa`, metadata, and SHA-256.

- [ ] **Step 1: Verify the complete branch without trusting prior output**

```powershell
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
python build-system/Make/ValidateGRVMgram.py source
python -m py_compile build-system/Make/ValidateGRVMgram.py
git diff --check
git status --short --branch
```

Expected: tests and validators pass. `git status` is clean before integration. If the Ghost fix is still uncommitted at this point, stop and complete its designated implementation-plan task before pushing.

- [ ] **Step 2: Perform final public-reference scans**

```powershell
rg -n -i "t\.me/ayugram|docs\.ayugram|boosty\.to/ayugram|github\.com/AyuGram|crowdin\.com/project/ayugram|@ayugram|UQA4i8U8|bc1qdk|0x405589|8ZHQp|TRpbaj" submodules/AyuGramSettingsUI submodules/AyuGramLib submodules/TelegramUI Telegram/BUILD
rg -n '"AyuGram Settings"|"AyuGram"|\[AyuGram\]' submodules/AyuGramSettingsUI submodules/AyuGramLib submodules/TelegramUI
```

Expected: no matches. Internal identifiers without quotes remain and are intentionally ignored.

- [ ] **Step 3: Push the implementation branch as a backup without triggering CI**

```powershell
git push -u origin codex/grvmgram-full-parity
```

Expected: push succeeds; current workflow does not run because automatic push trigger is `master` only.

- [ ] **Step 4: Fast-forward master and trigger exactly one final build**

```powershell
git switch master
git pull --ff-only origin master
git merge --ff-only codex/grvmgram-full-parity
git push origin master
```

Expected: no merge commit; one push event on `master`.

- [ ] **Step 5: Resolve the run ID for the exact pushed SHA**

```powershell
$sha = git rev-parse HEAD
do {
    $runs = gh run list --workflow build.yml --branch master --commit $sha --event push --limit 1 --json databaseId,status,url | ConvertFrom-Json
    if (-not $runs) {
        Start-Sleep -Seconds 5
    }
} until ($runs)
$runId = $runs[0].databaseId
$runId
$runs[0].url
```

Expected: one run whose head SHA equals `$sha`.

- [ ] **Step 6: Monitor continuously without blocking Codex communication**

Start this as a long-running PTY command with a 30-second first yield:

```powershell
gh run watch $runId --exit-status --interval 30
```

Poll the returned terminal session every 30-45 seconds. Send a concise progress update to the user at least once per minute while the build runs.

- [ ] **Step 7: Diagnose a failed run from complete logs**

If `gh run watch` exits non-zero:

```powershell
New-Item -ItemType Directory -Force "build\ci\$runId"
gh run download $runId -n build-log -D "build\ci\$runId"
gh run view $runId --log-failed
rg -n -C 8 "error:|fatal error|FAILED" "build\ci\$runId\build_log.txt"
```

Classify the failure from evidence:

- Compiler/linker/source failure: add the smallest reproducible local/static regression test, commit the focused fix, push `master`, resolve the new run ID from the new SHA, and return to Step 6.
- Confirmed transient GitHub/Xcode/network failure with no source error: run `gh run rerun $runId --failed`, then monitor the rerun.
- Missing/malformed IPA: fix Collect/validator logic or the proven build output path; do not mark the run successful.

- [ ] **Step 8: Download and independently validate the successful artifact**

```powershell
New-Item -ItemType Directory -Force "build\ci\$runId"
gh run download $runId -n GRVMgram-ipa -D "build\ci\$runId"
python build-system/Make/ValidateGRVMgram.py ipa "build\ci\$runId\GRVMgram.ipa"
Get-FileHash "build\ci\$runId\GRVMgram.ipa" -Algorithm SHA256
gh run view $runId --json conclusion,url,headSha
```

Expected:

- conclusion `success`;
- artifact `GRVMgram-ipa` exists;
- validator reports `display_name` and `bundle_name` as `GRVMgram`;
- ZIP contains one `Payload/*.app`, a non-empty executable, and both localization tables;
- validator and `Get-FileHash` report the final SHA-256.

- [ ] **Step 9: Report the installable result**

Return to the user:

- successful GitHub Actions run ID and URL;
- exact head SHA;
- artifact name `GRVMgram-ipa`;
- IPA filename `GRVMgram.ipa`;
- app version/build and bundle ID printed by the validator;
- SHA-256;
- confirmation that the IPA opened as ZIP, contained `Payload/*.app`, and passed EN/RU/public-brand checks.

Do not claim iPhone runtime behavior is verified until the user installs and tests the IPA.

---

## Final Self-Review Checklist

- Every GRVMgram-specific visible string is resource-backed; stock Telegram strings still use `PresentationStrings`.
- English and Russian key sets and format tokens are identical.
- Russian follows Telegram's selected language, not only the iOS system language.
- Main settings contain no About/Project/Links header or original-project links.
- Other contains no Boosty, crypto, donation, or dead Associate Links rows.
- No public/loggable `AyuGram` literal remains; the two internal legacy storage literals remain unchanged.
- App, extensions, theme file description, settings row, alerts, archives, menus, crash UI, and artifact use GRVMgram.
- Internal Bazel target/module/hook/database names remain unchanged.
- Missing IPA is a hard workflow failure.
- Successful IPA is independently validated after download.
- Only one final `master` push is used unless a proven CI failure requires a focused fix and replacement run.
