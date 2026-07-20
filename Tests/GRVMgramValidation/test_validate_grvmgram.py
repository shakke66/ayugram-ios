from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import plistlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPOSITORY_ROOT / "build-system" / "Make" / "ValidateGRVMgram.py"
SPEC = importlib.util.spec_from_file_location("validate_grvmgram", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


REQUIRED_KEYS = {
    "GRVMgram.Brand.Name": "GRVMgram",
    "GRVMgram.Streamer.Title": "Streamer",
    "GRVMgram.Streamer.Info": "Recording privacy information",
    "GRVMgram.Streamer.Cover": "Privacy cover",
    "GRVMgram.Crash.Export": "Export local logs",
    "GRVMgram.Chat.DeletedMark.Default": "\U0001F9F9",
    "GRVMgram.Chat.EditedMark.Default": "edited",
    "GRVMgram.Ghost.ActiveCount": "%d of %@ enabled",
}
REPOSITORY_ENGLISH = VALIDATOR.parse_strings(
    REPOSITORY_ROOT / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
)
REPOSITORY_RUSSIAN = VALIDATOR.parse_strings(
    REPOSITORY_ROOT / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"
)
REPOSITORY_ENUM_KEYS = set(
    VALIDATOR.extract_grvmgram_string_keys(
        REPOSITORY_ROOT
        / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
    )
)
if set(REPOSITORY_ENGLISH) != set(REPOSITORY_RUSSIAN) or set(
    REPOSITORY_ENGLISH
) != REPOSITORY_ENUM_KEYS:
    raise RuntimeError("Repository GRVMgram localization inventory is inconsistent")


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def strings_file(entries: dict[str, str]) -> str:
    return "\n".join(
        f"{json.dumps(key, ensure_ascii=False)} = "
        f"{json.dumps(value, ensure_ascii=False)};"
        for key, value in entries.items()
    ) + "\n"


def create_localization_tree(
    root: Path,
    *,
    russian_extra: bool = False,
    enum_extra: bool = False,
    russian_token: str | None = None,
    empty_key: str | None = None,
    omit_keys: set[str] | None = None,
    english_overrides: dict[str, str] | None = None,
    russian_overrides: dict[str, str] | None = None,
) -> None:
    english = dict(REQUIRED_KEYS)
    russian = dict(REQUIRED_KEYS)
    russian["GRVMgram.Streamer.Title"] = "Streamer RU"
    russian["GRVMgram.Chat.EditedMark.Default"] = "\u0438\u0437\u043c\u0435\u043d\u0435\u043d\u043e"
    for key in omit_keys or set():
        english.pop(key)
        russian.pop(key)
    english.update(english_overrides or {})
    russian.update(russian_overrides or {})
    if russian_extra:
        russian["GRVMgram.Extra"] = "Extra"
    if russian_token is not None:
        russian["GRVMgram.Ghost.ActiveCount"] = russian_token
    if empty_key is not None:
        russian[empty_key] = ""

    write(
        root / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings",
        strings_file(english),
    )
    write(
        root / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings",
        strings_file(russian),
    )
    enum_keys = list(english)
    if enum_extra:
        enum_keys.append("GRVMgram.Extra")
    enum_cases = "\n".join(
        f'    case key{index} = "{key}"'
        for index, key in enumerate(enum_keys)
    )
    write(
        root
        / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift",
        "public enum GRVMgramStringKey: String, CaseIterable {\n"
        + enum_cases
        + "\n}\n",
    )


def create_source_tree(root: Path) -> None:
    create_localization_tree(root)
    build_values = "\n".join("<string>GRVMgram</string>" for _ in range(9))
    write(
        root / "Telegram/BUILD",
        build_values + "\n<string>GRVMgram Color Theme File</string>\n",
    )
    write(
        root / "Telegram/Telegram-iOS/Config-Fork.xcconfig",
        "APP_NAME = GRVMgram\n",
    )
    for language in ("ar", "ko"):
        write(root / f"Telegram/Telegram-iOS/{language}.lproj/InfoPlist.strings", "")
    write(root / ".github/workflows/build.yml", workflow_fixture())


def workflow_fixture() -> str:
    return """name: GRVMgram build
jobs:
  build:
    runs-on: macos-26
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: 'recursive'
          fetch-depth: '0'
      - name: Validate GRVMgram sources
        run: |
          python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v
          python3 build-system/Make/ValidateGRVMgram.py source
      - name: Fetch submodules by exact commit
        run: |
          set -e
          fetch_sub() {
            local path="$1"; local url="$2"; local sha="$3"
            echo "=== $path @ $sha ==="
            rm -rf "$path"
            git clone --filter=blob:none "$url" "$path"
            git -C "$path" checkout -q "$sha"
            git -C "$path" submodule update --init --recursive --depth 1 || true
          }
          fetch_sub build-system/bazel-rules/apple_support       https://github.com/bazelbuild/apple_support.git                a99414ad848c3aeb84640934352ecc85d8a937f5
          fetch_sub build-system/bazel-rules/rules_apple         https://github.com/ali-fareed/rules_apple.git                  1791d916de4083388f22e20248d8b010d23f0d6b
          fetch_sub build-system/bazel-rules/rules_swift         https://github.com/bazelbuild/rules_swift.git                  9dce728ed1e9168ec8c912fcd3443dad48a286fe
          fetch_sub build-system/bazel-rules/rules_xcodeproj     https://github.com/MobileNativeFoundation/rules_xcodeproj.git   997f2db058596f91663e54782b79490de87208da
          fetch_sub build-system/bazel-rules/sourcekit-bazel-bsp https://github.com/spotify/sourcekit-bazel-bsp.git             feea27cfc88eccc58af0cfe5674444e945cfb75f
          fetch_sub submodules/LottieCpp/lottiecpp               https://github.com/ali-fareed/lottiecpp.git                    4a3144b5d527429f7bbd0f07003cb372bf8939ce
          fetch_sub submodules/TgVoipWebrtc/tgcalls              https://github.com/TelegramMessenger/tgcalls.git               8099768559edb0efd2d1b300090c18141226e9a8
          fetch_sub submodules/rlottie/rlottie                   https://github.com/TelegramMessenger/rlottie.git               67f103bc8b625f2a4a9e94f1d8c7bd84c5a08d1d
          fetch_sub third-party/XcodeGen                         https://github.com/yonaskolb/XcodeGen.git                      53cb43cb66908a28812d7629d03fed94c9827a24
          fetch_sub third-party/dav1d/dav1d                      https://github.com/ali-fareed/dav1d.git                        330e20672e85f9de1678dccd6957845898ef57a1
          fetch_sub third-party/libvpx/libvpx                    https://github.com/webmproject/libvpx.git                      e7bfd8b6c230a6824e7fd1efa2378a7322986128
          fetch_sub third-party/td/td                            https://github.com/tdlib/td.git                                e894536b2f46caad93f997448d2daff9431b19dd
          fetch_sub third-party/webrtc/webrtc                    https://github.com/ali-fareed/webrtc.git                       d5c77d3588c9353dd48b80430d2ffb41dafef177
          echo "=== submodule sizes ==="
          du -sh build-system/bazel-rules/* submodules/rlottie/rlottie third-party/webrtc/webrtc 2>/dev/null || true
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
      - name: Upload build log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: build-log
          path: build_log.txt
          if-no-files-found: warn
"""


def replace_workflow_step(value: str, name: str, replacement: str) -> str:
    header = f"      - name: {name}\n"
    start = value.index(header)
    end = value.find("      - ", start + len(header))
    if end == -1:
        end = len(value)
    return value[:start] + replacement + value[end:]


def create_ipa(
    path: Path,
    *,
    display_name: str = "GRVMgram",
    bundle_name: str = "GRVMgram",
    include_payload: bool = True,
    include_executable: bool = True,
    empty_executable: bool = False,
    include_tables: bool = True,
    russian_entries: dict[str, str] | None = None,
    extra_apps: int = 0,
    unsafe_member: bool = False,
    malformed_info: bool = False,
    truncated_xml_info: bool = False,
    symlink_executable: bool = False,
    directory_executable: bool = False,
    directory_info: bool = False,
    directory_localization: bool = False,
    dos_directory_info: bool = False,
    dos_directory_localization: bool = False,
    drive_member: bool = False,
    case_collision: bool = False,
    fifo_member: bool = False,
    prefix_collision: bool = False,
    standard_extra_roots: bool = False,
    payload_sibling_file: bool = False,
    payload_sibling_directory: bool = False,
    unrelated_root: bool = False,
    decoy_app_file: bool = False,
    metadata_omissions: set[str] | None = None,
    metadata_overrides: dict[str, object] | None = None,
    omit_ipa_keys: set[str] | None = None,
    omit_russian_ipa_keys: set[str] | None = None,
    english_overrides: dict[str, str] | None = None,
    russian_overrides: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if not include_payload:
            archive.writestr("README.txt", b"not an ipa")
            return
        app_roots = ["Payload/Telegram.app"] + [
            f"Payload/Extra{index}.app" for index in range(extra_apps)
        ]
        for app_root in app_roots:
            info = {
                "CFBundleDisplayName": display_name,
                "CFBundleName": bundle_name,
                "CFBundleExecutable": "Telegram",
                "CFBundleIdentifier": "ph.telegra.Telegraph",
                "CFBundleShortVersionString": "12.6.2",
                "CFBundleVersion": "3000",
            }
            for key in metadata_omissions or set():
                info.pop(key, None)
            info.update(metadata_overrides or {})
            if malformed_info:
                info_bytes = b"not a plist"
            elif truncated_xml_info:
                info_bytes = b"<?xml version=\"1.0\"?><plist><dict>"
            else:
                info_bytes = plistlib.dumps(info)
            info_path = f"{app_root}/Info.plist"
            if directory_info or dos_directory_info:
                info_entry = zipfile.ZipInfo(info_path)
                if dos_directory_info:
                    info_entry.create_system = 0
                    info_entry.external_attr = 0x10
                else:
                    info_entry.create_system = 3
                    info_entry.external_attr = (stat.S_IFDIR | 0o755) << 16
                archive.writestr(info_entry, info_bytes)
            else:
                archive.writestr(info_path, info_bytes)
            if include_executable:
                executable = b"" if empty_executable else b"Mach-O fixture"
                if symlink_executable:
                    executable_info = zipfile.ZipInfo(f"{app_root}/Telegram")
                    executable_info.create_system = 3
                    executable_info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(executable_info, b"Telegram")
                elif directory_executable:
                    executable_info = zipfile.ZipInfo(f"{app_root}/Telegram")
                    executable_info.create_system = 3
                    executable_info.external_attr = (stat.S_IFDIR | 0o755) << 16
                    archive.writestr(executable_info, b"directory fixture")
                else:
                    archive.writestr(f"{app_root}/Telegram", executable)
            if include_tables:
                english = dict(REPOSITORY_ENGLISH)
                russian = dict(REPOSITORY_RUSSIAN)
                for key in omit_ipa_keys or set():
                    english.pop(key)
                    russian.pop(key)
                for key in omit_russian_ipa_keys or set():
                    russian.pop(key)
                if russian_entries is not None:
                    russian = russian_entries
                english.update(english_overrides or {})
                russian.update(russian_overrides or {})
                english_path = f"{app_root}/en.lproj/GRVMgram.strings"
                english_bytes = strings_file(english).encode("utf-8")
                if directory_localization or dos_directory_localization:
                    english_entry = zipfile.ZipInfo(english_path)
                    if dos_directory_localization:
                        english_entry.create_system = 0
                        english_entry.external_attr = 0x10
                    else:
                        english_entry.create_system = 3
                        english_entry.external_attr = (stat.S_IFDIR | 0o755) << 16
                    archive.writestr(english_entry, english_bytes)
                else:
                    archive.writestr(english_path, english_bytes)
                archive.writestr(
                    f"{app_root}/ru.lproj/GRVMgram.strings",
                    strings_file(russian).encode("utf-8"),
                )
        if unsafe_member:
            archive.writestr("Payload/Telegram.app/../escape", b"unsafe")
        if drive_member:
            archive.writestr("C:/escape", b"unsafe")
        if case_collision:
            archive.writestr("Payload/Telegram.app/info.plist", b"collision")
        if fifo_member:
            fifo = zipfile.ZipInfo("Payload/Telegram.app/runtime.fifo")
            fifo.create_system = 3
            fifo.external_attr = (stat.S_IFIFO | 0o644) << 16
            archive.writestr(fifo, b"")
        if prefix_collision:
            archive.writestr("Payload", b"not a directory")
        if standard_extra_roots:
            for name in (
                "SwiftSupport/iphoneos/libswiftCore.dylib",
                "WatchKitSupport2/WK",
                "Symbols/Telegram.app.dSYM/Contents/Info.plist",
                "BCSymbolMaps/fixture.bcsymbolmap",
                "META-INF/MANIFEST.MF",
                "OnDemandResources/example.assetpack/Info.plist",
                "AssetPackManifest.plist",
                "iTunesMetadata.plist",
                "iTunesArtwork",
                "iTunesArtwork@2x",
                "iTunesArtwork@2x~ipad",
            ):
                archive.writestr(name, b"standard IPA fixture")
        if payload_sibling_file:
            archive.writestr("Payload/Extra.txt", b"unexpected Payload sibling")
        if payload_sibling_directory:
            sibling = zipfile.ZipInfo("Payload/Extras/")
            sibling.create_system = 3
            sibling.external_attr = (stat.S_IFDIR | 0o755) << 16
            archive.writestr(sibling, b"")
        if unrelated_root:
            archive.writestr("README.txt", b"unrelated")
        if decoy_app_file:
            archive.writestr("Payload/Decoy.app", b"not an app directory")


class StringsTests(unittest.TestCase):
    def test_parse_strings_parses_entry_after_leading_block_comment(self) -> None:
        parsed = VALIDATOR.parse_strings_text(
            '/* comment */ "EXTRA" = "value";\n',
            "fixture.strings",
        )
        self.assertEqual(parsed, {"EXTRA": "value"})

    def test_parse_strings_detects_duplicate_after_block_comment(self) -> None:
        source = '"A" = "one";\n/* comment */ "A" = "two";\n'
        with self.assertRaisesRegex(VALIDATOR.ValidationError, "duplicate key A"):
            VALIDATOR.parse_strings_text(source, "fixture.strings")

    def test_parse_strings_handles_comments_without_changing_quoted_values(self) -> None:
        source = (
            "/* leading\n"
            "   block */\n"
            '"A" /* between */ = "https://host/path/* literal */ // value"; '
            "/* trailing */\n"
            '"B" = "two"; // trailing line comment\n'
        )
        self.assertEqual(
            VALIDATOR.parse_strings_text(source, "fixture.strings"),
            {
                "A": "https://host/path/* literal */ // value",
                "B": "two",
            },
        )

    def test_parse_strings_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.strings"
            write(path, '"A" = "one";\n"A" = "two";\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "duplicate key A"):
                VALIDATOR.parse_strings(path)

    def test_parse_strings_rejects_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.strings"
            path.write_bytes(b'"A" = "\xff";\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "strict UTF-8"):
                VALIDATOR.parse_strings(path)

    def test_localizations_require_identical_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root, russian_extra=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_require_enum_key_parity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root, enum_extra=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_require_ordered_format_token_parity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root, russian_token="%@ of %d enabled")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "format-token mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_format_tokens_return_complete_foundation_specifiers_in_order(self) -> None:
        value = (
            "values: %ld %lld %02d %.2f %08.2f %zd "
            "%2$-08.3lld %*.*f %@ %% and 100% off"
        )
        self.assertEqual(
            VALIDATOR.format_tokens(value),
            [
                "%ld",
                "%lld",
                "%02d",
                "%.2f",
                "%08.2f",
                "%zd",
                "%2$-08.3lld",
                "%*.*f",
                "%@",
            ],
        )

    def test_format_tokens_ignore_natural_percent_words(self) -> None:
        for value in ("100% off", "100% discount", "100% for", "50% larger"):
            with self.subTest(value=value):
                self.assertEqual(VALIDATOR.format_tokens(value), [])

    def test_localizations_reject_changed_format_token_length(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(
                root,
                english_overrides={"GRVMgram.Ghost.ActiveCount": "Total: %ld"},
                russian_overrides={"GRVMgram.Ghost.ActiveCount": "Total: %lld"},
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "format-token mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_reject_dropped_extended_format_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(
                root,
                english_overrides={
                    "GRVMgram.Ghost.ActiveCount": "Count %02d, ratio %.2f, size %zd"
                },
                russian_overrides={
                    "GRVMgram.Ghost.ActiveCount": "Count %02d, size %zd"
                },
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "format-token mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_allow_literal_percent_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(
                root,
                english_overrides={"GRVMgram.Ghost.ActiveCount": "Save 100% off"},
                russian_overrides={"GRVMgram.Ghost.ActiveCount": "\u0421\u043a\u0438\u0434\u043a\u0430 100%"},
            )
            VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_commented_and_unrelated_enum_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            keys = [key for key in REQUIRED_KEYS if key != "GRVMgram.Crash.Export"]
            cases = "\n".join(
                f'    case key{index} = "{key}"' for index, key in enumerate(keys)
            )
            write(
                enum_path,
                "public enum GRVMgramStringKey: String, CaseIterable {\n"
                + cases
                + '\n    // case missing = "GRVMgram.Crash.Export"\n}\n'
                + "private enum UnrelatedStringKey: String {\n"
                + '    case missing = "GRVMgram.Crash.Export"\n}\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_require_nonempty_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root, empty_key="GRVMgram.Streamer.Info")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "empty value"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_fake_enum_declarations_and_comment_braces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            cases = "\n".join(
                f'    case key{index} = "{key}"' for index, key in enumerate(REQUIRED_KEYS)
            )
            write(
                enum_path,
                "/* public enum GRVMgramStringKey: String {\n"
                'case fake = "Fake"\n}\n*/\n'
                "public enum GRVMgramStringKey: String, CaseIterable {\n"
                "    // }\n" + cases + "\n}\n",
            )
            VALIDATOR.validate_localizations(root)

    def test_localizations_reject_fake_enum_declaration_inside_string(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            cases = "\n".join(
                f'case key{index} = "{key}"' for index, key in enumerate(REQUIRED_KEYS)
            )
            write(
                enum_path,
                'let fake = """\n'
                "public enum GRVMgramStringKey: String {\n"
                + cases
                + '\n}\n"""\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "missing GRVMgramStringKey enum"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_fake_enum_case_inside_string(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            cases = "\n".join(
                f'    case key{index} = "{key}"'
                for index, key in enumerate(REQUIRED_KEYS)
                if key != "GRVMgram.Crash.Export"
            )
            write(
                enum_path,
                "public enum GRVMgramStringKey: String, CaseIterable {\n"
                + cases
                + '\n    let fake = """\n'
                '    case fake = "GRVMgram.Crash.Export"\n'
                '    """\n}\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_nested_enum_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            cases = "\n".join(
                f'    case key{index} = "{key}"'
                for index, key in enumerate(REQUIRED_KEYS)
                if key != "GRVMgram.Crash.Export"
            )
            write(
                enum_path,
                "public enum GRVMgramStringKey: String, CaseIterable {\n"
                + cases
                + "\n    private enum Nested: String {\n"
                + '        case fake = "GRVMgram.Crash.Export"\n'
                + "    }\n}\n",
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_nested_same_name_enum_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            complete_cases = "\n".join(
                f'        case nested{index} = "{key}"'
                for index, key in enumerate(REQUIRED_KEYS)
            )
            incomplete_cases = "\n".join(
                f'    case key{index} = "{key}"'
                for index, key in enumerate(REQUIRED_KEYS)
                if key != "GRVMgram.Crash.Export"
            )
            write(
                enum_path,
                "private enum DecoyContainer {\n"
                "    public enum GRVMgramStringKey: String {\n"
                + complete_cases
                + "\n    }\n}\n"
                "public enum GRVMgramStringKey: String, CaseIterable {\n"
                + incomplete_cases
                + "\n}\n",
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_regex_braces_before_nested_enum_decoy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            complete_cases = "\n".join(
                f'        case nested{index} = "{key}"'
                for index, key in enumerate(REQUIRED_KEYS)
            )
            incomplete_cases = "\n".join(
                f'    case key{index} = "{key}"'
                for index, key in enumerate(REQUIRED_KEYS)
                if key != "GRVMgram.Crash.Export"
            )
            write(
                enum_path,
                "private enum DecoyContainer {\n"
                "    static let closingBrace = /}/\n"
                "    public enum GRVMgramStringKey: String {\n"
                + complete_cases
                + "\n    }\n}\n"
                "public enum GRVMgramStringKey: String, CaseIterable {\n"
                + incomplete_cases
                + "\n}\n",
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_ignore_returned_regex_braces_before_nested_enum(self) -> None:
        for return_expression in ("return /}/", "return /* comment */ /}/"):
            with self.subTest(expression=return_expression), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_localization_tree(root)
                enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
                complete_cases = "\n".join(
                    f'        case nested{index} = "{key}"'
                    for index, key in enumerate(REQUIRED_KEYS)
                )
                incomplete_cases = "\n".join(
                    f'    case key{index} = "{key}"'
                    for index, key in enumerate(REQUIRED_KEYS)
                    if key != "GRVMgram.Crash.Export"
                )
                write(
                    enum_path,
                    "private enum DecoyContainer {\n"
                    "    static func closingBrace() -> Regex<Substring> {\n"
                    f"        {return_expression}\n"
                    "    }\n"
                    "    public enum GRVMgramStringKey: String {\n"
                    + complete_cases
                    + "\n    }\n}\n"
                    "public enum GRVMgramStringKey: String, CaseIterable {\n"
                    + incomplete_cases
                    + "\n}\n",
                )
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "Swift key mismatch"):
                    VALIDATOR.validate_localizations(root)

    def test_localizations_reject_duplicate_top_level_public_enum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            value = enum_path.read_text(encoding="utf-8")
            write(enum_path, value + value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "duplicate.*GRVMgramStringKey"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_reject_implicit_direct_enum_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            enum_path = root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
            value = enum_path.read_text(encoding="utf-8").replace(
                "\n}\n",
                "\n    case implicitExtra\n}\n",
            )
            write(enum_path, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "explicit single string"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_require_retained_resource_keys(self) -> None:
        for key in REQUIRED_KEYS:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_localization_tree(root, omit_keys={key})
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "missing required"):
                    VALIDATOR.validate_localizations(root)

    def test_localizations_require_exact_deleted_and_edited_values(self) -> None:
        mutations = {
            "GRVMgram.Brand.Name": "OtherBrand",
            "GRVMgram.Chat.DeletedMark.Default": "deleted",
            "GRVMgram.Chat.EditedMark.Default": "changed",
        }
        for key, value in mutations.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_localization_tree(
                    root,
                    english_overrides={key: value},
                    russian_overrides={key: value},
                )
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "unexpected values"):
                    VALIDATOR.validate_localizations(root)

    def test_localizations_reject_whitespace_only_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(
                root,
                english_overrides={"GRVMgram.Streamer.Info": "   "},
                russian_overrides={"GRVMgram.Streamer.Info": "  "},
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "empty value"):
                VALIDATOR.validate_localizations(root)

    def test_localizations_accept_matching_keys_and_format_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            VALIDATOR.validate_localizations(root)


class BrandingTests(unittest.TestCase):
    def test_repository_has_no_public_ayugram_branding(self) -> None:
        VALIDATOR.validate_public_branding(REPOSITORY_ROOT)

    def test_repository_workflow_satisfies_release_contract(self) -> None:
        try:
            VALIDATOR.validate_workflow(REPOSITORY_ROOT)
        except VALIDATOR.ValidationError as error:
            self.fail(str(error))

    def test_repository_settings_ui_has_no_hard_coded_text(self) -> None:
        VALIDATOR.validate_settings_ui_literals(REPOSITORY_ROOT)

    def test_brand_scan_skips_literal_parser_without_ayugram_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Clean.swift",
                'let title = "Telegram"\n',
            )
            with mock.patch.object(
                VALIDATOR,
                "iter_swift_literals",
                side_effect=AssertionError("clean source should not be tokenized"),
            ):
                VALIDATOR.validate_public_branding(root)

    def test_legacy_storage_and_internal_identifiers_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift",
                'let queue = "com.ayugram.deletedMessagesDB"\n'
                "let sharedKey = ApplicationSpecificSharedDataKeys.ayuGramSettings\n"
                "let settings = AyuGramSettings.self\n"
                "let feature = AyuGramFeatureManager.shared\n"
                "let hook = AyuGramHooks.shouldSaveDeletedMessages\n"
                "let codingKey = \"associateLinks\"\n",
            )
            write(
                root / "submodules/TelegramUI/Sources/AppDelegate.swift",
                'let databaseURL = documentsURL.appendingPathComponent("ayugram_messages.db")\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_legacy_storage_literals_are_rejected_outside_storage_paths(self) -> None:
        fixtures = (
            (
                "submodules/TelegramUI/Sources/PublicTitle.swift",
                'let title = "ayugram_messages.db"\n',
            ),
            (
                "submodules/TelegramUI/Sources/PublicQueue.swift",
                'let title = "com.ayugram.deletedMessagesDB"\n',
            ),
            (
                "Telegram/Telegram-iOS/Info.plist",
                "<plist><dict><string>ayugram_messages.db</string></dict></plist>\n",
            ),
        )
        for relative_path, source in fixtures:
            with self.subTest(path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write(root / relative_path, source)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                    VALIDATOR.validate_public_branding(root)

    def test_public_ayugram_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Bad.swift",
                'let title = "AyuGram Settings"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_compile_time_concatenated_swift_branding_is_rejected(self) -> None:
        fixtures = (
            (
                'let title = "Ayu" /* compile-time join */ +\n'
                '    "Gram Settings"\n',
                "public/loggable",
            ),
            (
                'let url = "https://t.me/ayu" + "gram"\n',
                "forbidden public token",
            ),
            (
                'let endpoint = "dpa" + "ste"\n',
                "forbidden public token",
            ),
            (
                'let title = ("Ayu") + (("Gram Settings"))\n',
                "public/loggable",
            ),
            (
                'let title = (("Ayu") + ("Gram")) + " Settings"\n',
                "public/loggable",
            ),
            (
                'let title = "Ayu" + ("Gram" + " Settings")\n',
                "public/loggable",
            ),
            (
                'let title = "Ayu\\("Gram") Settings"\n',
                "public/loggable",
            ),
            (
                'let url = "https://t.me/" + ("ayu" + "gram")\n',
                "forbidden public token",
            ),
        )
        for source, message in fixtures:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write(root / "submodules/TelegramUI/Sources/Bad.swift", source)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, message):
                    VALIDATOR.validate_public_branding(root)

    def test_unrelated_swift_tokens_are_not_reconstructed_as_branding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Clean.swift",
                'let tuple = ("Ayu", "Gram Settings")\n'
                'let dynamic = "Ayu" + component + "Gram Settings"\n'
                'let transformed = normalize("Ayu") + ("Gram Settings")\n'
                'let escapedCall = `repeat`("Ayu") + ("Gram Settings")\n'
                "let exteraClient = Service()\n"
                '// let oldURL = "https://t.me/ayugram"\n'
                '/* let oldTitle = "Ayu" + "Gram Settings" */\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_dynamic_swift_interpolations_are_not_reconstructed_as_branding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Dynamic.swift",
                'let identifier = "Ayu\\(component)Gram Settings"\n'
                'let function = "Ayu\\(normalize("Gram")) Settings"\n'
                'let escapedCall = "Ayu\\(`repeat`("Gram")) Settings"\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_identifier_shaped_public_ayugram_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Bad.swift",
                'let title = "AyuGramTelemetry"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_quoted_legacy_route_is_rejected_as_public_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramLib/Sources/Bad.swift",
                'let route = ".ayuGramSettings"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_plist_public_ayugram_string_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "Telegram/Telegram-iOS/Info.plist",
                "<?xml version=\"1.0\"?><plist><dict>"
                "<key>CFBundleDisplayName</key><string>AyuGram</string>"
                "</dict></plist>\n",
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "plist public"):
                VALIDATOR.validate_public_branding(root)

    def test_plist_padded_legacy_storage_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "Telegram/Telegram-iOS/Info.plist",
                "<plist><dict><key>Database</key>"
                "<string> ayugram_messages.db </string>"
                "</dict></plist>\n",
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "plist public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_settings_ui_hard_coded_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Bad.swift",
                'let title = "Visible Settings Label"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "hard-coded GRVMgram Settings UI text"):
                VALIDATOR.validate_public_branding(root)

    def test_settings_ui_technical_literals_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = (
                "default",
                "Black",
                "PremiumTurbo",
                "Menlo",
                "Courier-Bold",
                "associateLinks",
            )
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Allowed.swift",
                "\n".join(f'let value = "{value}"' for value in values) + "\n",
            )
            VALIDATOR.validate_public_branding(root)

    def test_runtime_swift_interpolation_and_unicode_escape_are_not_public_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Runtime.swift",
                'let count = "count \\(value)"\nlet icon = "\\u{2713}"\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_multiline_and_escaped_swift_public_branding_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Bad.swift",
                'let title = """\nAyuGram Telemetry\n"""\n'
                'let escaped = "\\u{41}yuGram Settings"\n'
                'let raw = #"AyuGram Raw"#\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_escaped_quote_branding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "submodules/TelegramUI/Sources/Quote.swift", 'let a = "prefix \\"AyuGram\\""\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_comment_marker_inside_string_branding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "submodules/TelegramUI/Sources/Comment.swift", 'let b = "AyuGram /* not a comment */ suffix"\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_unicode_escape_branding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "submodules/TelegramUI/Sources/Escape.swift", 'let c = "\\u{41}yuGram Settings"\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_block_comment_marker_inside_string_branding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "submodules/TelegramUI/Sources/Block.swift", 'let x = "prefix /* not a comment */ AyuGram"\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_line_comment_marker_inside_string_branding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "submodules/TelegramUI/Sources/Line.swift", 'let x = "prefix // AyuGram"\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_multiline_comment_marker_inside_triple_literal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "submodules/TelegramUI/Sources/Triple.swift", 'let x = """\nprefix /* AyuGram */ suffix\n"""\n')
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_escaped_triple_quote_keeps_comment_like_branding_in_literal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/EscapedTriple.swift",
                'let title = """\nprefix \\\""" /* AyuGram */ suffix\n"""\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_raw_triple_escaped_delimiter_keeps_line_comment_in_literal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/EscapedRawTriple.swift",
                'let title = #"""\nprefix \\#"""#\n// AyuGram\nsuffix\n"""#\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_raw_interpolation_requires_matching_hash_delimiter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Raw.swift",
                'let title = #"\\(AyuGram)"#\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_genuine_raw_interpolation_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Raw.swift",
                'let title = #"\\#(internalIdentifier)"#\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_swift_nested_literal_in_normal_interpolation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Nested.swift",
                'let title = "\\(identity(wrap("AyuGram Telemetry")))"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_nested_literal_in_raw_interpolation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/NestedRaw.swift",
                'let title = #"\\#(identity(#"AyuGram Telemetry"#))"#\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_normal_literal_nested_in_raw_interpolation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/NestedRawNormal.swift",
                'let title = #"\\#(identity("AyuGram Telemetry"))"#\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_identifier_only_interpolations_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Interpolation.swift",
                'let normal = "\\(formatter(value))"\n'
                'let raw = #"\\#(formatter(value))"#\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_swift_escaped_interpolation_opener_remains_literal_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/EscapedInterpolation.swift",
                'let title = "\\\\(AyuGram Telemetry)"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_regex_parentheses_do_not_end_interpolation(self) -> None:
        for regex_literal in ("#/[)][)]/#", "/[)][)]/"):
            with self.subTest(regex=regex_literal), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write(
                    root / "submodules/TelegramUI/Sources/RegexInterpolation.swift",
                    f'let title = "\\(identity({regex_literal}, "AyuGram Telemetry"))"\n',
                )
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                    VALIDATOR.validate_public_branding(root)

    def test_swift_normal_triple_line_continuation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Continuation.swift",
                'let title = """Ayu\\\nGram Telemetry"""\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_indented_triple_line_continuation_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/IndentedContinuation.swift",
                'let title = """\n    Ayu\\\n    Gram Telemetry\n    """\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_raw_triple_line_continuation_is_hash_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/RawContinuation.swift",
                'let title = #"""Ayu\\#\nGram Telemetry"""#\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)

    def test_swift_noncontinuation_backslashes_preserve_line_break(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/NonContinuation.swift",
                'let escaped = """Ayu\\\\\nGram Telemetry"""\n'
                'let mismatchedRaw = #"""Ayu\\\nGram Telemetry"""#\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_cross_module_hard_coded_prompt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Bad.swift",
                'let prompt = "Send voice message?"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "hard-coded UI text"):
                VALIDATOR.validate_public_branding(root)

    def test_cross_module_prompt_is_allowed_in_grvmgram_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings",
                '"Prompt" = "Send voice message?";\n',
            )
            VALIDATOR.validate_public_branding(root)

    def test_settings_ui_available_message_literal_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Available.swift",
                "@available(*, deprecated, message: "
                '"Use grvmDeletedMessagesController(context:peerId:threadId:)")\n'
                "public func compatibilityEntryPoint() {}\n",
            )
            VALIDATOR.validate_settings_ui_literals(root)

    def test_settings_ui_available_message_text_is_rejected_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Runtime.swift",
                'let title = "Use grvmDeletedMessagesController(context:peerId:threadId:)"\n',
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "hard-coded GRVMgram Settings UI text",
            ):
                VALIDATOR.validate_settings_ui_literals(root)

    def test_settings_ui_nested_available_message_label_is_not_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/AyuGramSettingsUI/Sources/Nested.swift",
                "@available(*, deprecated, renamed: helper("
                'message: "Visible Settings Label"))\n'
                "public func compatibilityEntryPoint() {}\n",
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "hard-coded GRVMgram Settings UI text",
            ):
                VALIDATOR.validate_settings_ui_literals(root)

    def test_dpaste_endpoint_does_not_match_pasteboard_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/TelegramUI/Sources/Clean.swift",
                'let type = "DiscardPasteboardAlert"\n',
            )
            VALIDATOR.validate_public_branding(root)
            write(
                root / "submodules/TelegramUI/Sources/Bad.swift",
                'let endpoint = "https://dpaste.org/api"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "dpaste"):
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

    def test_future_media_picker_and_gallery_roots_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/MediaPickerUI/Sources/Bad.swift",
                'let title = "AyuGram menu"\n',
            )
            write(
                root / "submodules/GalleryUI/Sources/Bad.swift",
                'let url = "https://t.me/ayugram"\n',
            )
            with self.assertRaises(VALIDATOR.ValidationError) as raised:
                VALIDATOR.validate_public_branding(root)
            self.assertIn("MediaPickerUI", str(raised.exception))
            self.assertIn("GalleryUI", str(raised.exception))

    def test_all_submodule_roots_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(
                root / "submodules/FutureGRVMUI/Sources/Bad.swift",
                'let title = "AyuGram Future UI"\n',
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "public/loggable"):
                VALIDATOR.validate_public_branding(root)


class SourceTests(unittest.TestCase):
    def test_validate_source_accepts_a_complete_synthetic_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            VALIDATOR.validate_source(root)

    def test_workflow_requires_exact_checkout_contract(self) -> None:
        mutations = (
            (
                "          fetch-depth: '0'\n",
                "          fetch-depth: '0'\n          repository: other/project\n",
            ),
            (
                "          fetch-depth: '0'\n",
                "          fetch-depth: '0'\n          ref: unreviewed\n",
            ),
            ("actions/checkout@v4", "actions/checkout@v3"),
        )
        for original, replacement in mutations:
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                write(
                    workflow,
                    workflow.read_text(encoding="utf-8").replace(
                        original, replacement, 1
                    ),
                )
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "checkout"):
                    VALIDATOR.validate_workflow(root)

    def test_validate_workflow_rejects_legacy_artifact_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(workflow, workflow.read_text(encoding="utf-8") + "name: Telegram-ipa\n")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "legacy public artifact"):
                VALIDATOR.validate_workflow(root)

    def test_main_reports_missing_source_files_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_localization_tree(root)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = VALIDATOR.main(["source", str(root)])
            self.assertEqual(result, 1)
            self.assertIn("ERROR:", stderr.getvalue())

    def test_workflow_rejects_commented_source_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(
                workflow,
                workflow.read_text(encoding="utf-8").replace(
                    "          python3 build-system/Make/ValidateGRVMgram.py source",
                    "          # python3 build-system/Make/ValidateGRVMgram.py source",
                ),
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_expression_that_disables_source_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "      - name: Validate GRVMgram sources\n",
                "      - name: Validate GRVMgram sources\n        if: ${{ false }}\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_disabled_release_job(self) -> None:
        for field in ("if: ${{ false }}", "continue-on-error: true"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                value = workflow.read_text(encoding="utf-8").replace(
                    "  build:\n",
                    f"  build:\n    {field}\n",
                )
                write(workflow, value)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "release job"):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_wrong_source_step_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            checkout = "      - uses: actions/checkout@v4\n"
            value = value.replace(checkout, "")
            value = value.replace(
                "      - name: Fetch submodules by exact commit\n",
                checkout + "      - name: Fetch submodules by exact commit\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "workflow step order"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_echoed_source_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(
                workflow,
                workflow.read_text(encoding="utf-8").replace(
                    "          python3 build-system/Make/ValidateGRVMgram.py source",
                    '          echo "python3 build-system/Make/ValidateGRVMgram.py source"',
                ),
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_source_commands_in_uncalled_function(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = replace_workflow_step(
                workflow.read_text(encoding="utf-8"),
                "Validate GRVMgram sources",
                "      - name: Validate GRVMgram sources\n"
                "        run: |\n"
                "          validate_sources() {\n"
                "            python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v\n"
                "            python3 build-system/Make/ValidateGRVMgram.py source\n"
                "          }\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_source_commands_in_here_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = replace_workflow_step(
                workflow.read_text(encoding="utf-8"),
                "Validate GRVMgram sources",
                "      - name: Validate GRVMgram sources\n"
                "        run: |\n"
                "          cat <<'COMMANDS'\n"
                "          python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v\n"
                "          python3 build-system/Make/ValidateGRVMgram.py source\n"
                "          COMMANDS\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_source_commands_inside_false_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = replace_workflow_step(
                workflow.read_text(encoding="utf-8"),
                "Validate GRVMgram sources",
                "      - name: Validate GRVMgram sources\n"
                "        run: |\n"
                "          if false; then\n"
                "            python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v\n"
                "            python3 build-system/Make/ValidateGRVMgram.py source\n"
                "          fi\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_reversed_source_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            first = "          python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v\n"
            second = "          python3 build-system/Make/ValidateGRVMgram.py source\n"
            value = workflow.read_text(encoding="utf-8").replace(
                first + second,
                second + first,
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_hash_suffixes_that_are_not_comments(self) -> None:
        mutations = (
            (
                "python3 build-system/Make/ValidateGRVMgram.py source",
                "python3 build-system/Make/ValidateGRVMgram.py source#disabled",
                "source step",
            ),
            (
                "uses: actions/upload-artifact@v4",
                "uses: actions/upload-artifact@v4#wrong",
                "Upload IPA",
            ),
        )
        for original, replacement, expected in mutations:
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                write(
                    workflow,
                    workflow.read_text(encoding="utf-8").replace(
                        original,
                        replacement,
                        1,
                    ),
                )
                with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_required_steps_reject_unexpected_execution_fields(self) -> None:
        fields = (
            (
                "Validate GRVMgram sources",
                "        shell: bash -c 'true' -- {0}\n",
            ),
            (
                "Fetch submodules by exact commit",
                "        env:\n          PATH: /tmp/bypass\n",
            ),
            (
                "Collect IPA",
                "        working-directory: /tmp\n",
            ),
            (
                "Validate GRVMgram IPA",
                "        shell: bash -c 'true' -- {0}\n",
            ),
            (
                "Upload IPA",
                "        env:\n          PATH: /tmp/bypass\n",
            ),
            (
                "Upload build log",
                "        env:\n          PATH: /tmp/bypass\n",
            ),
        )
        for step_name, field in fields:
            with self.subTest(step=step_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                value = workflow.read_text(encoding="utf-8").replace(
                    f"      - name: {step_name}\n",
                    f"      - name: {step_name}\n{field}",
                )
                write(workflow, value)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, step_name):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_extra_independent_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "jobs:\n",
                "jobs:\n"
                "  lint:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: true\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "exactly one workflow job"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_skipped_dependency_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "jobs:\n  build:\n",
                "jobs:\n"
                "  skipped:\n"
                "    if: ${{ false }}\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: true\n"
                "  build:\n"
                "    needs: skipped\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "exactly one workflow job"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_unapproved_release_job_fields(self) -> None:
        fields = (
            "    needs: setup\n",
            "    env:\n      PATH: /tmp/bypass\n",
            "    defaults:\n      run:\n        shell: bash\n",
            "    strategy:\n      fail-fast: false\n",
            "    container: ubuntu:latest\n",
            "    services:\n      helper:\n        image: alpine\n",
            "    uses: owner/repository/.github/workflows/build.yml@main\n",
        )
        for field in fields:
            with self.subTest(field=field.splitlines()[0]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                value = workflow.read_text(encoding="utf-8").replace(
                    "  build:\n",
                    "  build:\n" + field,
                )
                write(workflow, value)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "release job"):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_top_level_env_and_defaults(self) -> None:
        fields = (
            "env:\n  PATH: /tmp/bypass\n",
            "defaults:\n  run:\n    shell: bash -c 'true' -- {0}\n",
        )
        for field in fields:
            with self.subTest(field=field.splitlines()[0]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                value = workflow.read_text(encoding="utf-8").replace(
                    "jobs:\n",
                    field + "jobs:\n",
                )
                write(workflow, value)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "workflow-level"):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_quoted_scope_and_execution_keys(self) -> None:
        mutations = (
            (
                "jobs:\n",
                "jobs:\n"
                "  \"extra\":\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: true\n",
                "exactly one workflow job",
            ),
            (
                "      - name: Validate GRVMgram sources\n",
                "      - name: Validate GRVMgram sources\n"
                "        \"shell\": bash -c 'true' -- {0}\n",
                "Validate GRVMgram sources",
            ),
            (
                "jobs:\n",
                "\"env\":\n  PATH: /tmp/bypass\njobs:\n",
                "workflow-level",
            ),
        )
        for original, replacement, expected in mutations:
            with self.subTest(replacement=replacement.splitlines()[0]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                value = workflow.read_text(encoding="utf-8").replace(
                    original,
                    replacement,
                    1,
                )
                write(workflow, value)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_noop_fetch_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = replace_workflow_step(
                workflow.read_text(encoding="utf-8"),
                "Fetch submodules by exact commit",
                "      - name: Fetch submodules by exact commit\n"
                "        run: true\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Fetch submodules"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_fetch_sha_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "a99414ad848c3aeb84640934352ecc85d8a937f5",
                "b99414ad848c3aeb84640934352ecc85d8a937f5",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Fetch submodules"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_reordered_collect_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            copy = '          cp -L "$IPA" "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"\n'
            verify = '          test -s "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"\n'
            value = value.replace(copy + verify, verify + copy)
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Collect IPA"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_requires_collect_validate_upload_adjacency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "      - name: Validate GRVMgram IPA\n",
                "      - name: Intervening package step\n"
                "        run: true\n"
                "      - name: Validate GRVMgram IPA\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "adjacent"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_requires_exact_validate_ipa_scalar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = replace_workflow_step(
                workflow.read_text(encoding="utf-8"),
                "Validate GRVMgram IPA",
                "      - name: Validate GRVMgram IPA\n"
                "        if: success()\n"
                "        run: |\n"
                "          python3 build-system/Make/ValidateGRVMgram.py ipa artifacts/GRVMgram.ipa\n"
                "          true\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Validate GRVMgram IPA"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_release_gates_reject_truthy_continue_on_error(self) -> None:
        step_names = (
            "Validate GRVMgram sources",
            "Fetch submodules by exact commit",
            "Collect IPA",
            "Validate GRVMgram IPA",
            "Upload IPA",
        )
        for step_name in step_names:
            with self.subTest(step=step_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                create_source_tree(root)
                workflow = root / ".github/workflows/build.yml"
                value = workflow.read_text(encoding="utf-8").replace(
                    f"      - name: {step_name}\n",
                    f"      - name: {step_name}\n        continue-on-error: true\n",
                )
                write(workflow, value)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "incomplete|disabled|non-blocking"):
                    VALIDATOR.validate_workflow(root)

    def test_workflow_release_gates_allow_explicit_false_continue_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            for step_name in (
                "Validate GRVMgram sources",
                "Fetch submodules by exact commit",
                "Collect IPA",
                "Validate GRVMgram IPA",
                "Upload IPA",
            ):
                value = value.replace(
                    f"      - name: {step_name}\n",
                    f"      - name: {step_name}\n        continue-on-error: false\n",
                )
            write(workflow, value)
            VALIDATOR.validate_workflow(root)

    def test_workflow_requires_source_immediately_after_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(
                workflow,
                workflow.read_text(encoding="utf-8").replace(
                    "      - name: Validate GRVMgram sources\n",
                    "      - name: Intervening step\n        run: true\n"
                    "      - name: Validate GRVMgram sources\n",
                ),
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "immediately after checkout"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_nonexecutable_source_step_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            value = value.replace(
                "        run: |\n"
                "          python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v\n"
                "          python3 build-system/Make/ValidateGRVMgram.py source\n",
                "        env:\n"
                "          FAKE_COMMANDS: |\n"
                "            python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v\n"
                "            python3 build-system/Make/ValidateGRVMgram.py source\n"
                "        run: echo bypassed\n"
                "        continue-on-error: true\n",
            )
            value = value.replace(
                "      - name: Fetch submodules by exact commit\n",
                "      - name: Intervening after source\n        run: echo intervening\n"
                "      - name: Fetch submodules by exact commit\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "source step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_upload_fields_hidden_in_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            value = value.replace(
                "        with:\n          name: GRVMgram-ipa\n          path: artifacts/GRVMgram.ipa\n          if-no-files-found: error\n",
                "        env:\n          name: GRVMgram-ipa\n          path: artifacts/GRVMgram.ipa\n          if-no-files-found: error\n"
                "        with:\n          name: Wrong\n          path: artifacts/wrong\n          if-no-files-found: warn\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Upload IPA"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_requires_nonempty_build_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(workflow, workflow.read_text(encoding="utf-8").replace("          path: build_log.txt", "          path: "))
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "build log"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_requires_exact_build_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(
                workflow,
                workflow.read_text(encoding="utf-8").replace(
                    "          path: build_log.txt",
                    "          path: build.log",
                ),
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "build log"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_nested_env_release_step_fakes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            value = value.replace(
                "      - name: Upload IPA\n",
                "      - name: Upload IPA\n        env:\n          if: success()\n          uses: actions/upload-artifact@v4\n          name: GRVMgram-ipa\n          path: artifacts/GRVMgram.ipa\n          if-no-files-found: error\n",
            ).replace(
                "      - name: Upload IPA\n        if: success()\n        uses: actions/upload-artifact@v4\n",
                "      - name: Upload IPA\n        if: success()\n        uses: echo fake\n",
            )
            value = value.replace("        uses: actions/upload-artifact@v4\n", "        uses: echo fake\n")
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Upload IPA"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_checkout_only_nested_in_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "      - uses: actions/checkout@v4\n",
                "      - name: Fake setup\n"
                "        env:\n"
                "          uses: actions/checkout@v4\n"
                "        run: echo fake\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "actions/checkout"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_required_steps_split_across_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "      - name: Collect IPA\n",
                "  package:\n"
                "    steps:\n"
                "      - name: Collect IPA\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "same job"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_duplicate_required_step_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "jobs:\n",
                "jobs:\n"
                "  duplicate:\n"
                "    steps:\n"
                "      - name: Upload build log\n"
                "        run: echo duplicate\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "duplicate workflow step"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_rejects_build_log_path_hidden_in_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8").replace(
                "        with:\n"
                "          name: build-log\n"
                "          path: build_log.txt\n",
                "        with:\n"
                "          name: build-log\n"
                "        env:\n"
                "          path: build_log.txt\n",
            )
            write(workflow, value)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "build log"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_requires_always_uploaded_build_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            write(
                workflow,
                workflow.read_text(encoding="utf-8").replace("if: always()", "if: success()"),
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "build log"):
                VALIDATOR.validate_workflow(root)

    def test_workflow_requires_build_log_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_source_tree(root)
            workflow = root / ".github/workflows/build.yml"
            value = workflow.read_text(encoding="utf-8")
            write(workflow, value[: value.index("      - name: Upload build log\n")])
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "build log"):
                VALIDATOR.validate_workflow(root)


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

    def test_ipa_requires_all_release_metadata_keys(self) -> None:
        keys = (
            "CFBundleIdentifier",
            "CFBundleShortVersionString",
            "CFBundleVersion",
        )
        for key in keys:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "GRVMgram.ipa"
                create_ipa(path, metadata_omissions={key})
                with self.assertRaisesRegex(VALIDATOR.ValidationError, key):
                    VALIDATOR.validate_ipa(path)

    def test_ipa_requires_string_release_metadata_values(self) -> None:
        keys = (
            "CFBundleIdentifier",
            "CFBundleShortVersionString",
            "CFBundleVersion",
        )
        for key in keys:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "GRVMgram.ipa"
                create_ipa(path, metadata_overrides={key: 42})
                with self.assertRaisesRegex(VALIDATOR.ValidationError, key):
                    VALIDATOR.validate_ipa(path)

    def test_ipa_requires_nonempty_release_metadata_values(self) -> None:
        keys = (
            "CFBundleIdentifier",
            "CFBundleShortVersionString",
            "CFBundleVersion",
        )
        for key in keys:
            for value in ("", "   ", "\t"):
                with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "GRVMgram.ipa"
                    create_ipa(path, metadata_overrides={key: value})
                    with self.assertRaisesRegex(VALIDATOR.ValidationError, key):
                        VALIDATOR.validate_ipa(path)

    def test_ipa_requires_exact_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Telegram.ipa"
            create_ipa(path)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "GRVMgram.ipa"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_multiple_payload_apps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, extra_apps=1)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "exactly one Payload/.+app"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_direct_app_file_decoy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, decoy_app_file=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "exactly one Payload/.+app"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_unsafe_member_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, unsafe_member=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "unsafe"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_windows_drive_member_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, drive_member=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "unsafe member path"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_canonical_member_path_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, case_collision=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "ambiguous canonical"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_symbolic_link_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, symlink_executable=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "symbolic link"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_directory_mode_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, directory_executable=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "regular file"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_mandatory_resources_to_be_regular_files(self) -> None:
        fixtures = (
            {"directory_info": True},
            {"directory_localization": True},
            {"dos_directory_info": True},
            {"dos_directory_localization": True},
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "GRVMgram.ipa"
                create_ipa(path, **fixture)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "regular file"):
                    VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_fifo_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, fifo_member=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "file type"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_file_directory_prefix_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, prefix_collision=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "prefix collision"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_accepts_documented_standard_extra_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, standard_extra_roots=True)
            VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_payload_siblings_outside_main_app(self) -> None:
        fixtures = (
            ({"payload_sibling_file": True}, "Payload/Extra.txt"),
            ({"payload_sibling_directory": True}, "Payload/Extras"),
        )
        for fixture, member in fixtures:
            with self.subTest(member=member), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "GRVMgram.ipa"
                create_ipa(path, **fixture)
                with self.assertRaisesRegex(
                    VALIDATOR.ValidationError,
                    "unsupported Payload member",
                ) as raised:
                    VALIDATOR.validate_ipa(path)
                self.assertIn(member, str(raised.exception))

    def test_ipa_rejects_unrelated_top_level_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, unrelated_root=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "unsupported IPA root"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_wrong_bundle_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, display_name="Telegram", bundle_name="Telegram")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "CFBundleDisplayName"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_a_nonempty_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, empty_executable=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "executable is empty"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_the_declared_executable_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, include_executable=False)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "missing main app executable"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_rejects_a_malformed_info_plist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, malformed_info=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "invalid app Info.plist"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_wraps_truncated_xml_info_plist_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, truncated_xml_info=True)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "invalid app Info.plist"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_both_localization_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, include_tables=False)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "missing IPA resource"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_localization_key_token_and_value_parity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(
                path,
                russian_overrides={"GRVMgram.Ghost.ActiveCount": "%@ of %d enabled"},
            )
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "format-token mismatch"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_localization_key_parity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, omit_russian_ipa_keys={"GRVMgram.Ghost.ActiveCount"})
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "key mismatch"):
                VALIDATOR.validate_ipa(path)

    def test_ipa_requires_nonempty_localization_values(self) -> None:
        fixtures = (
            {"english_overrides": {"GRVMgram.Ghost.ActiveCount": "   "}},
            {"russian_overrides": {"GRVMgram.Ghost.ActiveCount": "  "}},
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "GRVMgram.ipa"
                create_ipa(path, **fixture)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "empty value"):
                    VALIDATOR.validate_ipa(path)

    def test_ipa_requires_repository_key_outside_legacy_minimum(self) -> None:
        key = "GRVMgram.Settings.Title"
        self.assertIn(key, REPOSITORY_ENUM_KEYS)
        self.assertNotIn(key, REQUIRED_KEYS)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(path, omit_ipa_keys={key})
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "IPA localization inventory mismatch",
            ) as raised:
                VALIDATOR.validate_ipa(path)
            self.assertIn(key, str(raised.exception))

    def test_ipa_rejects_keys_outside_repository_inventory(self) -> None:
        key = "GRVMgram.Unexpected"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            create_ipa(
                path,
                english_overrides={key: "Unexpected"},
                russian_overrides={key: "Unexpected"},
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "IPA localization inventory mismatch",
            ) as raised:
                VALIDATOR.validate_ipa(path)
            self.assertIn(key, str(raised.exception))

    def test_ipa_requires_retained_localization_keys_even_with_table_parity(self) -> None:
        for key in REQUIRED_KEYS:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "GRVMgram.ipa"
                create_ipa(path, omit_ipa_keys={key})
                with self.assertRaisesRegex(VALIDATOR.ValidationError, "missing required localization keys"):
                    VALIDATOR.validate_ipa(path)

    def test_corrupt_zip_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "GRVMgram.ipa"
            path.write_bytes(b"not a zip")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "valid ZIP"):
                VALIDATOR.validate_ipa(path)


if __name__ == "__main__":
    unittest.main()
