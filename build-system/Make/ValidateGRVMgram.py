#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import hashlib
import json
import plistlib
import re
import stat
import sys
import unicodedata
import zipfile
import zlib
from pathlib import Path
from xml.parsers import expat


class ValidationError(Exception):
    """Raised when a GRVMgram release contract is violated."""


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STRINGS_ENTRY_RE = re.compile(
    r'^\s*"((?:\\.|[^"\\])*)"\s*=\s*"((?:\\.|[^"\\])*)"\s*;\s*$'
)
SWIFT_ENUM_CASE_RE = re.compile(r"\bcase\b")
SWIFT_ENUM_DECL_RE = re.compile(
    r'\bpublic\s+enum\s+GRVMgramStringKey\s*:\s*String\b'
)
QUOTED_STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
PLIST_STRING_RE = re.compile(r"<string\b[^>]*>(.*?)</string\s*>", re.DOTALL | re.IGNORECASE)
FORMAT_TOKEN_RE = re.compile(
    r"%(?!%)"
    r"(?:\d+\$)?"
    r"[-+ #0']*"
    r"(?:\d+|\*(?:\d+\$)?)?"
    r"(?:\.(?:\d+|\*(?:\d+\$)?)?)?"
    r"(?:hh|ll|[hlqztjL])?"
    r"[@diouxXDOUfFeEgGaAcCsSpn]"
)
LETTER_RE = re.compile(r'[A-Za-z\u0400-\u04ff]')

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
    "ayugrambot",
    "extera",
    "dpaste",
    "UQA4i8U8vP3mYUZSV3KqDQEHPwmhninEqCkkKc7BITQ652de",
    "bc1qdk6qq4mzq5yap3fpy0qau3246w3m3uwac9f0xd",
    "0x405589857C8DFAb45B2027c68ad1e58877FDa347",
    "8ZHQpPxpsdRjsWoBcF1dmvRM5dB6zEhJ3jMBFZjYfyHs",
    "TRpbajq38qU8joThgAfKJLyEPbNjzsdPJ1",
)
ALLOWED_LEGACY_STORAGE_PATHS = {
    "com.ayugram.deletedMessagesDB": (
        "submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift"
    ),
    "ayugram_messages.db": "submodules/TelegramUI/Sources/AppDelegate.swift",
}
ALLOWED_SETTINGS_UI_LITERALS = {
    "",
    "\\n",
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
    "%.2f",
    "public.json",
    "grvmgram-filters-",
    "json",
    "associateLinks",
}
FORBIDDEN_CROSS_UI_LITERALS = {
    "Send sticker?",
    "Send GIF?",
    "Send voice message?",
    "Enable Ghost Mode to view stories privately",
    "AyuGram Settings",
    "Burn media?",
    "This permanently marks the media as viewed on Telegram.",
    "Preserved media is unavailable.",
    "Forward Local Copy",
    "Read Message",
    "This message can't be forwarded as a local copy.",
    "The local media is unavailable.",
}
REQUIRED_LOCALIZATION_KEYS = {
    "GRVMgram.Brand.Name",
    "GRVMgram.Streamer.Title",
    "GRVMgram.Streamer.Info",
    "GRVMgram.Streamer.Cover",
    "GRVMgram.Crash.Export",
    "GRVMgram.Chat.DeletedMark.Default",
    "GRVMgram.Chat.EditedMark.Default",
    "GRVMgram.Ghost.ActiveCount",
}
REQUIRED_LOCALIZATION_VALUES = {
    "GRVMgram.Brand.Name": ("GRVMgram", "GRVMgram"),
    "GRVMgram.Chat.DeletedMark.Default": ("\U0001F9F9", "\U0001F9F9"),
    "GRVMgram.Chat.EditedMark.Default": ("edited", "\u0438\u0437\u043c\u0435\u043d\u0435\u043d\u043e"),
}
RUNTIME_ROOTS = (
    "submodules",
    "Telegram/Telegram-iOS",
)
TEXT_SUFFIXES = {".swift", ".m", ".mm", ".plist", ".strings", ".xcconfig"}
SOURCE_RUN_LINES = (
    "python3 -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py' -v",
    "python3 build-system/Make/ValidateGRVMgram.py source",
)
FETCH_RUN_LINES = (
    "set -e",
    "fetch_sub() {",
    'local path="$1"; local url="$2"; local sha="$3"',
    'echo "=== $path @ $sha ==="',
    'rm -rf "$path"',
    'git clone --filter=blob:none "$url" "$path"',
    'git -C "$path" checkout -q "$sha"',
    'git -C "$path" submodule update --init --recursive --depth 1 || true',
    "}",
    "fetch_sub build-system/bazel-rules/apple_support       https://github.com/bazelbuild/apple_support.git                a99414ad848c3aeb84640934352ecc85d8a937f5",
    "fetch_sub build-system/bazel-rules/rules_apple         https://github.com/ali-fareed/rules_apple.git                  1791d916de4083388f22e20248d8b010d23f0d6b",
    "fetch_sub build-system/bazel-rules/rules_swift         https://github.com/bazelbuild/rules_swift.git                  9dce728ed1e9168ec8c912fcd3443dad48a286fe",
    "fetch_sub build-system/bazel-rules/rules_xcodeproj     https://github.com/MobileNativeFoundation/rules_xcodeproj.git   997f2db058596f91663e54782b79490de87208da",
    "fetch_sub build-system/bazel-rules/sourcekit-bazel-bsp https://github.com/spotify/sourcekit-bazel-bsp.git             feea27cfc88eccc58af0cfe5674444e945cfb75f",
    "fetch_sub submodules/LottieCpp/lottiecpp               https://github.com/ali-fareed/lottiecpp.git                    4a3144b5d527429f7bbd0f07003cb372bf8939ce",
    "fetch_sub submodules/TgVoipWebrtc/tgcalls              https://github.com/TelegramMessenger/tgcalls.git               8099768559edb0efd2d1b300090c18141226e9a8",
    "fetch_sub submodules/rlottie/rlottie                   https://github.com/TelegramMessenger/rlottie.git               67f103bc8b625f2a4a9e94f1d8c7bd84c5a08d1d",
    "fetch_sub third-party/XcodeGen                         https://github.com/yonaskolb/XcodeGen.git                      53cb43cb66908a28812d7629d03fed94c9827a24",
    "fetch_sub third-party/dav1d/dav1d                      https://github.com/ali-fareed/dav1d.git                        330e20672e85f9de1678dccd6957845898ef57a1",
    "fetch_sub third-party/libvpx/libvpx                    https://github.com/webmproject/libvpx.git                      e7bfd8b6c230a6824e7fd1efa2378a7322986128",
    "fetch_sub third-party/td/td                            https://github.com/tdlib/td.git                                e894536b2f46caad93f997448d2daff9431b19dd",
    "fetch_sub third-party/webrtc/webrtc                    https://github.com/ali-fareed/webrtc.git                       d5c77d3588c9353dd48b80430d2ffb41dafef177",
    'echo "=== submodule sizes ==="',
    "du -sh build-system/bazel-rules/* submodules/rlottie/rlottie third-party/webrtc/webrtc 2>/dev/null || true",
)
COLLECT_RUN_LINES = (
    "set -euo pipefail",
    "SOURCE_DIR=/Users/Shared/telegram-ios",
    'cd "$SOURCE_DIR"',
    'IPA="bazel-bin/Telegram/Telegram.ipa"',
    'if [ ! -e "$IPA" ]; then',
    'IPA="$(ls -1 bazel-out/*/bin/Telegram/Telegram.ipa 2>/dev/null | head -1 || true)"',
    "fi",
    'if [ -z "$IPA" ] || [ ! -e "$IPA" ]; then',
    'echo "ERROR: Telegram.ipa not found. Contents of bazel-bin/Telegram:"',
    "ls -la bazel-bin/Telegram/ 2>/dev/null | head -60 || true",
    "exit 1",
    "fi",
    'mkdir -p "$GITHUB_WORKSPACE/artifacts"',
    'cp -L "$IPA" "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"',
    'test -s "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"',
    'ls -lh "$GITHUB_WORKSPACE/artifacts/GRVMgram.ipa"',
)
VALIDATE_IPA_COMMAND = (
    "python3 build-system/Make/ValidateGRVMgram.py ipa artifacts/GRVMgram.ipa"
)
IPA_DIRECTORY_ROOTS = {
    "Payload",
    "SwiftSupport",
    "WatchKitSupport2",
    "Symbols",
    "BCSymbolMaps",
    "META-INF",
    "OnDemandResources",
}
IPA_FILE_ROOTS = {"AssetPackManifest.plist", "iTunesMetadata.plist"}
ITUNES_ARTWORK_RE = re.compile(r"iTunesArtwork(?:@\d+x)?(?:~ipad)?")
SWIFT_REGEX_PREFIX_KEYWORDS = {
    "await",
    "case",
    "guard",
    "if",
    "in",
    "return",
    "switch",
    "throw",
    "try",
    "where",
    "while",
    "yield",
}


def read_utf8(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValidationError(f"{path}: unable to read strict UTF-8: {error}") from error
    if "\ufffd" in value:
        raise ValidationError(f"{path}: contains U+FFFD replacement character")
    return value


def decode_strings_value(value: str, source: str, line_number: int) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"{source}:{line_number}: invalid escaped string: {error}"
        ) from error


def _mask_strings_comments(value: str, source: str) -> str:
    result: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    while index < len(value):
        if block_depth:
            if value.startswith("/*", index):
                block_depth += 1
                result.extend("  ")
                index += 2
                continue
            if value.startswith("*/", index):
                block_depth -= 1
                result.extend("  ")
                index += 2
                continue
            result.append("\n" if value[index] == "\n" else " ")
            index += 1
            continue
        if in_string:
            result.append(value[index])
            if value[index] == "\\" and index + 1 < len(value):
                result.append(value[index + 1])
                index += 2
                continue
            if value[index] == '"':
                in_string = False
            index += 1
            continue
        if value.startswith("//", index):
            while index < len(value) and value[index] != "\n":
                result.append(" ")
                index += 1
            continue
        if value.startswith("/*", index):
            block_depth = 1
            result.extend("  ")
            index += 2
            continue
        if value[index] == '"':
            in_string = True
        result.append(value[index])
        index += 1
    if block_depth:
        raise ValidationError(f"{source}: unterminated block comment")
    return "".join(result)


def parse_strings_text(value: str, source: str) -> dict[str, str]:
    if "\ufffd" in value:
        raise ValidationError(f"{source}: contains U+FFFD replacement character")
    result: dict[str, str] = {}
    uncommented = _mask_strings_comments(value, source)
    for line_number, line in enumerate(uncommented.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        match = STRINGS_ENTRY_RE.fullmatch(line)
        if match is None:
            raise ValidationError(f"{source}:{line_number}: invalid .strings entry")
        key = decode_strings_value(match.group(1), source, line_number)
        localized = decode_strings_value(match.group(2), source, line_number)
        if key in result:
            raise ValidationError(f"{source}:{line_number}: duplicate key {key}")
        result[key] = localized
    return result


def parse_strings(path: Path) -> dict[str, str]:
    return parse_strings_text(read_utf8(path), str(path))


def format_tokens(value: str) -> list[str]:
    scrubbed = value.replace("%%", "")
    result: list[str] = []
    for match in FORMAT_TOKEN_RE.finditer(scrubbed):
        token = match.group(0)
        if (
            token.startswith("% ")
            and match.end() < len(scrubbed)
            and scrubbed[match.end()].isalpha()
        ):
            continue
        result.append(token)
    return result


def validate_table_pair(
    english: dict[str, str],
    russian: dict[str, str],
    *,
    label: str,
) -> None:
    if set(english) != set(russian):
        missing_ru = sorted(set(english) - set(russian))
        extra_ru = sorted(set(russian) - set(english))
        raise ValidationError(
            f"{label} key mismatch: missing_ru={missing_ru}, extra_ru={extra_ru}"
        )
    for key in sorted(english):
        if not english[key].strip() or not russian[key].strip():
            raise ValidationError(f"{label}: empty value for {key}")
        english_tokens = format_tokens(english[key])
        russian_tokens = format_tokens(russian[key])
        if english_tokens != russian_tokens:
            raise ValidationError(
                f"{label} format-token mismatch for {key}: "
                f"{english_tokens} != {russian_tokens}"
            )


def validate_required_localization_contract(
    english: dict[str, str], russian: dict[str, str]
) -> None:
    missing_required = sorted(REQUIRED_LOCALIZATION_KEYS - set(english))
    if missing_required:
        raise ValidationError(f"missing required localization keys: {missing_required}")
    for key, expected in REQUIRED_LOCALIZATION_VALUES.items():
        actual = (english[key], russian[key])
        if actual != expected:
            raise ValidationError(f"unexpected values for {key}: {actual}")


def extract_grvmgram_string_keys(path: Path) -> list[str]:
    source = read_utf8(path)
    value = blank_swift_comments(source)
    code = mask_swift_literals(value)
    source_depths: list[int] = []
    source_depth = 0
    for character in code:
        source_depths.append(source_depth)
        if character == "{":
            source_depth += 1
        elif character == "}":
            source_depth -= 1

    declarations = [
        declaration
        for declaration in SWIFT_ENUM_DECL_RE.finditer(code)
        if source_depths[declaration.start()] == 0
    ]
    if not declarations:
        raise ValidationError(f"{path}: missing GRVMgramStringKey enum declaration")
    if len(declarations) != 1:
        raise ValidationError(
            f"{path}: duplicate top-level public GRVMgramStringKey declarations"
        )
    declaration = declarations[0]
    opening_brace = code.find("{", declaration.end())
    if opening_brace == -1:
        raise ValidationError(f"{path}: malformed GRVMgramStringKey enum declaration")
    depth = 0
    closing_brace = -1
    for index in range(opening_brace, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                closing_brace = index
                break
    if closing_brace == -1:
        raise ValidationError(f"{path}: unterminated GRVMgramStringKey enum")
    block = code[opening_brace + 1 : closing_brace]
    brace_depths: list[int] = []
    block_depth = 0
    for character in block:
        brace_depths.append(block_depth)
        if character == "{":
            block_depth += 1
        elif character == "}":
            block_depth -= 1
    literal_tokens = [
        (start, end, literal)
        for kind, start, end, _line, literal, _hashes in _iter_swift_tokens(source)
        if kind == "literal" and literal is not None
    ]
    keys: list[str] = []
    for case in SWIFT_ENUM_CASE_RE.finditer(block):
        if brace_depths[case.start()] != 0:
            continue
        statement_end = block.find("\n", case.end())
        if statement_end == -1:
            statement_end = len(block)
        statement = block[case.start() : statement_end]
        absolute_start = opening_brace + 1 + case.start()
        absolute_end = opening_brace + 1 + statement_end
        statement_literals = [
            literal
            for start, end, literal in literal_tokens
            if absolute_start <= start and end <= absolute_end
        ]
        explicit_single_case = re.fullmatch(
            r"case[ \t]+[A-Za-z_][A-Za-z0-9_]*[ \t]*=[ \t]*",
            statement,
        )
        if explicit_single_case is None or len(statement_literals) != 1:
            raise ValidationError(
                f"{path}: every direct enum case must be an explicit single string "
                "raw-value declaration"
            )
        keys.append(statement_literals[0])
    return keys


def _swift_literal_opening(value: str, index: int):
    hashes = 0
    while index + hashes < len(value) and value[index + hashes] == "#":
        hashes += 1
    quote = index + hashes
    if quote >= len(value) or value[quote] != '"':
        return None
    triple = value.startswith('"""', quote)
    quote_length = 3 if triple else 1
    return hashes, triple, quote, quote_length


def _swift_line_comment_end(value: str, index: int) -> int:
    end = value.find("\n", index)
    return len(value) if end == -1 else end


def _swift_block_comment_end(value: str, index: int) -> int:
    depth = 1
    index += 2
    while index < len(value) and depth:
        if value.startswith("/*", index):
            depth += 1
            index += 2
        elif value.startswith("*/", index):
            depth -= 1
            index += 2
        else:
            index += 1
    return index


def _swift_regex_opening(value: str, index: int):
    hashes = 0
    while index + hashes < len(value) and value[index + hashes] == "#":
        hashes += 1
    slash = index + hashes
    if slash >= len(value) or value[slash] != "/":
        return None
    if hashes:
        return hashes, slash
    if value.startswith(("//", "/*"), index):
        return None
    previous = index - 1
    while previous >= 0 and value[previous].isspace():
        previous -= 1
    if previous >= 0 and value[previous] not in "([{:;,=!?&|+-*%^~<>":
        word_end = previous + 1
        word_start = word_end
        while word_start > 0 and (
            value[word_start - 1].isalnum() or value[word_start - 1] == "_"
        ):
            word_start -= 1
        if value[word_start:word_end] not in SWIFT_REGEX_PREFIX_KEYWORDS:
            return None
    return 0, slash


def _scan_swift_regex(value: str, opening: tuple[int, int]) -> int:
    hashes, slash = opening
    closing = "/" + ("#" * hashes)
    cursor = slash + 1
    in_character_class = False
    while cursor < len(value):
        if value[cursor] == "\\":
            cursor += min(2, len(value) - cursor)
            continue
        if value[cursor] == "[":
            in_character_class = True
            cursor += 1
            continue
        if value[cursor] == "]" and in_character_class:
            in_character_class = False
            cursor += 1
            continue
        if not in_character_class and value.startswith(closing, cursor):
            return cursor + len(closing)
        cursor += 1
    return len(value)


def _scan_swift_interpolation(value: str, index: int, hashes: int):
    opener = "\\" + ("#" * hashes) + "("
    if not value.startswith(opener, index):
        return None
    tokens: list[tuple[str, int, int, str | None, int | None]] = []
    depth = 1
    cursor = index + len(opener)
    while cursor < len(value):
        if value.startswith("//", cursor):
            end = _swift_line_comment_end(value, cursor)
            tokens.append(("comment", cursor, end, None, None))
            cursor = end
            continue
        if value.startswith("/*", cursor):
            end = _swift_block_comment_end(value, cursor)
            tokens.append(("comment", cursor, end, None, None))
            cursor = end
            continue
        regex_opening = _swift_regex_opening(value, cursor)
        if regex_opening is not None:
            cursor = _scan_swift_regex(value, regex_opening)
            continue
        opening = _swift_literal_opening(value, cursor)
        if opening is not None:
            cursor, literal_tokens = _scan_swift_literal(
                value, cursor, opening
            )
            tokens.extend(literal_tokens)
            continue
        if value[cursor] == "(":
            depth += 1
        elif value[cursor] == ")":
            depth -= 1
            if depth == 0:
                return cursor + 1, tokens
        cursor += 1
    return None


def _scan_swift_literal(
    value: str,
    start: int,
    opening: tuple[int, bool, int, int],
):
    hashes, _triple, quote, quote_length = opening
    cursor = quote + quote_length
    segment_start = cursor
    segments: list[str] = []
    nested_tokens: list[tuple[str, int, int, str | None, int | None]] = []
    closing = ('"' * quote_length) + ("#" * hashes)
    escape_prefix = "\\" + ("#" * hashes)

    while cursor < len(value):
        interpolation = _scan_swift_interpolation(value, cursor, hashes)
        if interpolation is not None:
            segments.append(value[segment_start:cursor])
            cursor, interpolation_tokens = interpolation
            nested_tokens.extend(interpolation_tokens)
            segment_start = cursor
            continue
        escaped_closing = escape_prefix + closing
        if value.startswith(escaped_closing, cursor):
            cursor += len(escaped_closing)
            continue
        if value.startswith("\\", cursor):
            if hashes == 0:
                cursor += min(2, len(value) - cursor)
                continue
            if value.startswith(escape_prefix, cursor):
                cursor += len(escape_prefix)
                if cursor < len(value):
                    cursor += 1
                continue
        if value.startswith(closing, cursor):
            segments.append(value[segment_start:cursor])
            end = cursor + len(closing)
            break
        cursor += 1
    else:
        segments.append(value[segment_start:])
        end = len(value)

    literal = "".join(segments)
    outer = ("literal", start, end, literal, hashes)
    return end, [outer, *nested_tokens]


def _iter_swift_tokens(value: str):
    """Yield comments plus outer and interpolation-nested Swift literals."""
    tokens: list[tuple[str, int, int, str | None, int | None]] = []
    index = 0
    while index < len(value):
        if value.startswith("//", index):
            end = _swift_line_comment_end(value, index)
            tokens.append(("comment", index, end, None, None))
            index = end
            continue
        if value.startswith("/*", index):
            end = _swift_block_comment_end(value, index)
            tokens.append(("comment", index, end, None, None))
            index = end
            continue
        regex_opening = _swift_regex_opening(value, index)
        if regex_opening is not None:
            end = _scan_swift_regex(value, regex_opening)
            tokens.append(("regex", index, end, None, None))
            index = end
            continue
        opening = _swift_literal_opening(value, index)
        if opening is not None:
            index, literal_tokens = _scan_swift_literal(value, index, opening)
            tokens.extend(literal_tokens)
            continue
        index += 1

    line = 1
    line_cursor = 0
    for kind, start, end, literal, hashes in sorted(
        tokens, key=lambda token: (token[1], token[2])
    ):
        line += value.count("\n", line_cursor, start)
        line_cursor = start
        yield kind, start, end, line, literal, hashes


def _mask_swift_regions(value: str, *, mask_literals: bool) -> str:
    result = list(value)
    for kind, start, end, _line, _literal, _hashes in _iter_swift_tokens(value):
        if kind in {"comment", "regex"} or (kind == "literal" and mask_literals):
            for position in range(start, end):
                if value[position] != "\n":
                    result[position] = " "
    return "".join(result)


def blank_swift_comments(value: str) -> str:
    return _mask_swift_regions(value, mask_literals=False)


def mask_swift_literals(value: str) -> str:
    return _mask_swift_regions(value, mask_literals=True)


def normalize_swift_literal(value: str, hashes: int = 0) -> str:
    delimiter = "\\" + ("#" * hashes)
    escaped_delimiter = delimiter + "\\"
    result: list[str] = []
    index = 0
    while index < len(value):
        if hashes == 0 and value.startswith("\\\\", index):
            result.append("\\\\")
            index += 2
            continue
        if hashes and value.startswith(escaped_delimiter, index):
            result.append(escaped_delimiter)
            index += len(escaped_delimiter)
            continue
        if value.startswith(delimiter, index):
            escape_end = index + len(delimiter)
            if value.startswith("\r\n", escape_end):
                index = escape_end + 2
                while index < len(value) and value[index] in " \t":
                    index += 1
                continue
            if value.startswith("\n", escape_end):
                index = escape_end + 1
                while index < len(value) and value[index] in " \t":
                    index += 1
                continue
            unicode_escape = re.match(r"u\{([0-9A-Fa-f]+)\}", value[escape_end:])
            if unicode_escape is not None:
                try:
                    result.append(chr(int(unicode_escape.group(1), 16)))
                except ValueError:
                    result.append(value[index : escape_end + unicode_escape.end()])
                index = escape_end + unicode_escape.end()
                continue
        result.append(value[index])
        index += 1
    return "".join(result)


def iter_swift_literals(value: str):
    for kind, _start, _end, line, literal, hashes in _iter_swift_tokens(value):
        if kind == "literal":
            yield line, normalize_swift_literal(literal or "", hashes or 0)


def _swift_previous_code_index(value: str, index: int) -> int:
    index -= 1
    while index >= 0 and value[index].isspace():
        index -= 1
    return index


def _swift_next_code_index(value: str, index: int) -> int:
    while index < len(value) and value[index].isspace():
        index += 1
    return index


def _swift_group_opening_is_transparent(value: str, opening: int) -> bool:
    previous = _swift_previous_code_index(value, opening)
    if previous < 0:
        return True
    if value[previous].isalnum() or value[previous] == "_":
        word_end = previous + 1
        word_start = word_end
        while word_start > 0 and (
            value[word_start - 1].isalnum() or value[word_start - 1] == "_"
        ):
            word_start -= 1
        return value[word_start:word_end] in SWIFT_REGEX_PREFIX_KEYWORDS
    if value[previous] in ")]}`":
        return False
    if opening > 0 and value[opening - 1] in "\\#?!>":
        return False
    return True


def _swift_grouped_expression_bounds(
    value: str, start: int, end: int
) -> tuple[int, int]:
    while True:
        opening = _swift_previous_code_index(value, start)
        closing = _swift_next_code_index(value, end)
        if (
            opening < 0
            or closing >= len(value)
            or value[opening] != "("
            or value[closing] != ")"
            or not _swift_group_opening_is_transparent(value, opening)
        ):
            return start, end
        start = opening
        end = closing + 1


def _swift_skip_expression_trivia(value: str, index: int, limit: int) -> int:
    while index < limit:
        if value[index].isspace():
            index += 1
            continue
        if value.startswith("//", index):
            index = min(_swift_line_comment_end(value, index), limit)
            continue
        if value.startswith("/*", index):
            index = min(_swift_block_comment_end(value, index), limit)
            continue
        break
    return index


def _parse_swift_constant_string_expression(
    value: str, start: int, limit: int
) -> tuple[str, int] | None:
    def parse_term(index: int) -> tuple[str, int] | None:
        index = _swift_skip_expression_trivia(value, index, limit)
        if index >= limit:
            return None
        opening = _swift_literal_opening(value, index)
        if opening is not None:
            literal_end, _segments, constant = _analyze_swift_literal(
                value, index, opening
            )
            if constant is None or literal_end > limit:
                return None
            return constant, literal_end
        if value[index] != "(":
            return None
        nested = _parse_swift_constant_string_expression(value, index + 1, limit)
        if nested is None:
            return None
        nested_value, nested_end = nested
        nested_end = _swift_skip_expression_trivia(value, nested_end, limit)
        if nested_end >= limit or value[nested_end] != ")":
            return None
        return nested_value, nested_end + 1

    parsed = parse_term(start)
    if parsed is None:
        return None
    result, cursor = parsed
    while True:
        operator = _swift_skip_expression_trivia(value, cursor, limit)
        if operator >= limit or value[operator] != "+":
            return result, operator
        right = parse_term(operator + 1)
        if right is None:
            return result, operator
        right_value, cursor = right
        result += right_value


def _analyze_swift_literal(
    value: str,
    start: int,
    opening: tuple[int, bool, int, int],
) -> tuple[int, list[str], str | None]:
    hashes, _triple, quote, quote_length = opening
    cursor = quote + quote_length
    segment_start = cursor
    segments: list[str] = []
    components: list[str] = []
    is_constant = True
    closing = ('"' * quote_length) + ("#" * hashes)
    escape_prefix = "\\" + ("#" * hashes)
    interpolation_opener = escape_prefix + "("

    while cursor < len(value):
        interpolation = _scan_swift_interpolation(value, cursor, hashes)
        if interpolation is not None:
            segment = normalize_swift_literal(
                value[segment_start:cursor], hashes
            )
            segments.append(segment)
            components.append(segment)
            interpolation_end, _tokens = interpolation
            expression_start = cursor + len(interpolation_opener)
            expression_limit = interpolation_end - 1
            parsed = _parse_swift_constant_string_expression(
                value, expression_start, expression_limit
            )
            if parsed is None:
                is_constant = False
            else:
                interpolation_value, expression_end = parsed
                expression_end = _swift_skip_expression_trivia(
                    value, expression_end, expression_limit
                )
                if expression_end != expression_limit:
                    is_constant = False
                else:
                    components.append(interpolation_value)
            cursor = interpolation_end
            segment_start = cursor
            continue
        escaped_closing = escape_prefix + closing
        if value.startswith(escaped_closing, cursor):
            cursor += len(escaped_closing)
            continue
        if value.startswith("\\", cursor):
            if hashes == 0:
                cursor += min(2, len(value) - cursor)
                continue
            if value.startswith(escape_prefix, cursor):
                cursor += len(escape_prefix)
                if cursor < len(value):
                    cursor += 1
                continue
        if value.startswith(closing, cursor):
            segment = normalize_swift_literal(
                value[segment_start:cursor], hashes
            )
            segments.append(segment)
            components.append(segment)
            end = cursor + len(closing)
            break
        cursor += 1
    else:
        segment = normalize_swift_literal(value[segment_start:], hashes)
        segments.append(segment)
        components.append(segment)
        end = len(value)

    return end, segments, "".join(components) if is_constant else None


def iter_swift_string_expressions(value: str):
    tokens = list(_iter_swift_tokens(value))
    structural_source = list(value)
    for kind, start, end, _line, _literal, _hashes in tokens:
        if kind not in {"comment", "regex"}:
            continue
        for position in range(start, end):
            if value[position] != "\n":
                structural_source[position] = " "
    structural_value = "".join(structural_source)
    results: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    def add(line: int, literal: str) -> None:
        entry = (line, literal)
        if entry not in seen:
            seen.add(entry)
            results.append(entry)

    literal_tokens = [
        (start, line)
        for kind, start, _end, line, _literal, _hashes in tokens
        if kind == "literal"
    ]
    for start, line in literal_tokens:
        opening = _swift_literal_opening(value, start)
        if opening is None:
            continue
        _end, segments, constant = _analyze_swift_literal(value, start, opening)
        for segment in segments:
            add(line, segment)
        if constant is not None:
            add(line, constant)

        expression_start = start
        while True:
            parsed = _parse_swift_constant_string_expression(
                value, expression_start, len(value)
            )
            if parsed is None:
                break
            expression_value, expression_end = parsed
            add(line, expression_value)
            grouped_start, grouped_end = _swift_grouped_expression_bounds(
                structural_value, expression_start, expression_end
            )
            if grouped_start == expression_start and grouped_end == expression_end:
                break
            expression_start = grouped_start

    yield from results


def _swift_available_message_literal_starts(value: str, tokens: list[tuple]) -> set[int]:
    structural_source = list(value)
    for kind, start, end, _line, _literal, _hashes in tokens:
        if kind not in {"comment", "literal", "regex"}:
            continue
        for position in range(start, end):
            if value[position] != "\n":
                structural_source[position] = " "
    structural_value = "".join(structural_source)
    literal_ranges = [
        (start, end)
        for kind, start, end, _line, _literal, _hashes in tokens
        if kind == "literal"
    ]
    result: set[int] = set()
    for attribute in re.finditer(r"(?<![A-Za-z0-9_])@available\s*\(", structural_value):
        opening = structural_value.find("(", attribute.start(), attribute.end())
        depth = 1
        closing = -1
        for position in range(opening + 1, len(structural_value)):
            if structural_value[position] == "(":
                depth += 1
            elif structural_value[position] == ")":
                depth -= 1
                if depth == 0:
                    closing = position
                    break
        if closing == -1:
            continue
        attribute_body = structural_value[opening + 1 : closing]
        body_depths: list[int] = []
        body_depth = 0
        for character in attribute_body:
            body_depths.append(body_depth)
            if character == "(":
                body_depth += 1
            elif character == ")":
                body_depth -= 1
        for message in re.finditer(
            r"\bmessage\s*:",
            attribute_body,
        ):
            if body_depths[message.start()] != 0:
                continue
            message_end = opening + 1 + message.end()
            for literal_start, literal_end in literal_ranges:
                if literal_start < message_end:
                    continue
                if literal_end > closing:
                    break
                if not structural_value[message_end:literal_start].strip():
                    result.add(literal_start)
                break
    return result


def validate_localizations(root: Path) -> set[str]:
    english_path = root / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
    russian_path = root / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"
    enum_path = (
        root / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
    )
    for path in (english_path, russian_path, enum_path):
        if not path.is_file():
            raise ValidationError(f"missing required file: {path}")

    english = parse_strings(english_path)
    russian = parse_strings(russian_path)
    validate_table_pair(english, russian, label="localization")

    enum_keys = extract_grvmgram_string_keys(enum_path)
    if len(enum_keys) != len(set(enum_keys)):
        raise ValidationError("Swift enum contains duplicate localization key")
    if set(enum_keys) != set(english):
        missing_enum = sorted(set(english) - set(enum_keys))
        extra_enum = sorted(set(enum_keys) - set(english))
        raise ValidationError(
            f"Swift key mismatch: missing_enum={missing_enum}, extra_enum={extra_enum}"
        )

    validate_required_localization_contract(english, russian)
    return set(english)


def iter_runtime_files(root: Path):
    for relative_root in RUNTIME_ROOTS:
        directory = root / relative_root
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                yield path
    build_file = root / "Telegram/BUILD"
    if build_file.is_file():
        yield build_file


def is_allowed_legacy_storage_literal(root: Path, path: Path, literal: str) -> bool:
    allowed_path = ALLOWED_LEGACY_STORAGE_PATHS.get(literal)
    if allowed_path is None:
        return False
    try:
        relative_path = path.relative_to(root).as_posix()
    except ValueError:
        return False
    return relative_path == allowed_path


def validate_plist_public_values(root: Path, path: Path, value: str) -> list[str]:
    violations: list[str] = []
    for match in PLIST_STRING_RE.finditer(value):
        localized = html.unescape(match.group(1))
        if "ayugram" not in localized.casefold():
            continue
        if is_allowed_legacy_storage_literal(root, path, localized):
            continue
        line_number = value.count("\n", 0, match.start()) + 1
        display_value = localized.strip()
        violations.append(
            f"{path}:{line_number}: plist public/loggable AyuGram value {display_value}"
        )
    return violations


def validate_settings_ui_literals(root: Path) -> None:
    directory = root / "submodules/AyuGramSettingsUI/Sources"
    if not directory.is_dir():
        return
    violations: list[str] = []
    for path in directory.rglob("*.swift"):
        value = read_utf8(path)
        tokens = list(_iter_swift_tokens(value))
        available_message_starts = _swift_available_message_literal_starts(
            value, tokens
        )
        for kind, start, _end, line_number, literal, hashes in tokens:
            if kind != "literal" or start in available_message_starts:
                continue
            raw_literal = normalize_swift_literal(literal or "", hashes or 0)
            if raw_literal in ALLOWED_SETTINGS_UI_LITERALS:
                continue
            if LETTER_RE.search(raw_literal):
                violations.append(f"{path}:{line_number}: {raw_literal}")
    if violations:
        raise ValidationError(
            "hard-coded GRVMgram Settings UI text:\n" + "\n".join(violations)
        )


def contains_forbidden_public_token(value: str, token: str) -> bool:
    folded = value.casefold()
    if token == "dpaste":
        return re.search(r"(?<![a-z0-9_])dpaste(?![a-z0-9_])", folded) is not None
    return token.casefold() in folded


def swift_source_may_contain_ayugram(value: str) -> bool:
    folded = value.casefold()
    return (
        "ayugram" in folded
        or re.search(r"\\#*u\{", value, re.IGNORECASE) is not None
        or re.search(r"\\#*\r?\n", value) is not None
        or re.search(r"\\#*\(", value) is not None
    )


def validate_public_branding(root: Path) -> None:
    violations: list[str] = []
    for path in iter_runtime_files(root):
        value = read_utf8(path)
        folded = value.casefold()
        if path.suffix == ".plist":
            violations.extend(validate_plist_public_values(root, path, value))
        is_swift = path.suffix == ".swift"
        is_source = path.suffix in {".swift", ".m", ".mm"}
        if is_swift:
            should_scan_literals = (
                swift_source_may_contain_ayugram(value)
                or ('"' in value and "+" in value)
                or any(
                    contains_forbidden_public_token(value, token)
                    for token in FORBIDDEN_PUBLIC_TOKENS
                )
                or any(forbidden in value for forbidden in FORBIDDEN_CROSS_UI_LITERALS)
            )
            literal_entries = (
                list(iter_swift_string_expressions(value))
                if should_scan_literals
                else []
            )
            for line_number, literal in literal_entries:
                for token in FORBIDDEN_PUBLIC_TOKENS:
                    if contains_forbidden_public_token(literal, token):
                        violations.append(
                            f"{path}:{line_number}: forbidden public token {token}"
                        )
        else:
            for token in FORBIDDEN_PUBLIC_TOKENS:
                if contains_forbidden_public_token(value, token):
                    violations.append(f"{path}: forbidden public token {token}")
            should_scan_literals = "ayugram" in folded
            if is_source:
                should_scan_literals = swift_source_may_contain_ayugram(value)
            literal_entries = (
                list(iter_swift_literals(value))
                if should_scan_literals and is_source
                else []
            )
        if should_scan_literals:
            if not is_source:
                literal_entries = list(
                    (line_number, literal)
                    for line_number, line in enumerate(value.splitlines(), start=1)
                    for literal in QUOTED_STRING_RE.findall(line)
                )
            for line_number, literal in literal_entries:
                if "ayugram" not in literal.casefold():
                    continue
                if is_allowed_legacy_storage_literal(root, path, literal):
                    continue
                violations.append(
                    f"{path}:{line_number}: public/loggable AyuGram literal {literal}"
                )
        if is_swift:
            for line_number, literal in literal_entries:
                for forbidden in FORBIDDEN_CROSS_UI_LITERALS:
                    if forbidden in literal:
                        violations.append(
                            f"{path}:{line_number}: hard-coded UI text {forbidden}"
                        )
        elif is_source and any(
            forbidden in value for forbidden in FORBIDDEN_CROSS_UI_LITERALS
        ):
            for line_number, line in enumerate(value.splitlines(), start=1):
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


def _strip_workflow_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if quote is not None:
            if quote == '"' and escaped:
                escaped = False
            elif quote == '"' and character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index].rstrip()
    return line.rstrip()


def active_workflow_lines(value: str) -> list[str]:
    return [_strip_workflow_comment(line) for line in value.splitlines()]


def _workflow_field(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(
        r'(?:(?:"([^"]+)")|(?:\'([^\']+)\')|([A-Za-z0-9_.-]+|<<)):'
        r"\s*(.*?)\s*",
        value,
    )
    if match is None:
        return None
    key = match.group(1) or match.group(2) or match.group(3)
    return key, _workflow_scalar(match.group(4))


def workflow_top_level_fields(lines: list[str]) -> set[str]:
    fields: set[str] = set()
    for line in lines:
        if line.startswith(" ") or not line.strip():
            continue
        field = _workflow_field(line)
        if field is not None:
            fields.add(field[0])
    return fields


def workflow_job_names(lines: list[str]) -> list[str]:
    jobs: list[str] = []
    in_jobs = False
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped:
            in_jobs = stripped == "jobs:"
            continue
        if in_jobs and indent == 2 and stripped:
            field = _workflow_field(stripped)
            jobs.append(field[0] if field is not None else "<invalid>")
    return jobs


class WorkflowStep:
    def __init__(
        self,
        job: str,
        start: int,
        end: int,
        item_indent: int,
        name: str | None,
        job_fields: dict[str, str],
        fields: dict[str, str],
        with_fields: dict[str, str],
        run_lines: list[str],
    ) -> None:
        self.job = job
        self.start = start
        self.end = end
        self.item_indent = item_indent
        self.name = name
        self.job_fields = job_fields
        self.fields = fields
        self.with_fields = with_fields
        self.run_lines = run_lines


def _workflow_scalar(value: str) -> str:
    return value.strip().strip("'\"")


def workflow_steps(lines: list[str]) -> list[WorkflowStep]:
    """Parse only jobs/steps and retain each step's indentation scope."""
    specs: list[tuple[str, int, int, int, str]] = []
    in_jobs = False
    current_job: str | None = None
    in_steps = False
    current: list[object] | None = None
    job_fields: dict[str, dict[str, str]] = {}

    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped == "jobs:":
            in_jobs = True
            current_job = None
            in_steps = False
            continue
        if not in_jobs:
            continue
        job_field = _workflow_field(stripped) if indent == 2 else None
        if job_field is not None:
            if current is not None:
                current[2] = index
                specs.append(tuple(current))  # type: ignore[arg-type]
                current = None
            current_job = job_field[0]
            job_fields[current_job] = {}
            in_steps = False
            continue
        if current_job is None:
            continue
        field = _workflow_field(stripped) if indent == 4 else None
        if field is not None and field == ("steps", ""):
            in_steps = True
            continue
        if field is not None:
            job_fields[current_job][field[0]] = field[1]
        if in_steps and indent == 6 and re.match(r"^-\s+", stripped):
            if current is not None:
                current[2] = index
                specs.append(tuple(current))  # type: ignore[arg-type]
            current = [current_job, index, len(lines), indent, stripped[2:].strip()]

    if current is not None:
        specs.append(tuple(current))  # type: ignore[arg-type]

    parsed: list[WorkflowStep] = []
    for job, start, end, item_indent, item in specs:
        top_indent = item_indent + 2
        fields: dict[str, str] = {}
        with_fields: dict[str, str] = {}
        run_lines: list[str] = []
        item_field = _workflow_field(item)
        if item_field is not None:
            fields[item_field[0]] = item_field[1]
        section: str | None = "run" if fields.get("run") == "|" else None
        if section == "run":
            fields["run"] = "|"
        for line in lines[start + 1 : end]:
            indent = len(line) - len(line.lstrip(" "))
            field = _workflow_field(line[top_indent:]) if indent == top_indent else None
            if field is not None:
                key, field_value = field
                fields[key] = field_value
                section = key
                if key == "run" and fields[key] != "|":
                    run_lines.append(fields[key])
                continue
            if section == "with" and indent == top_indent + 2:
                nested = _workflow_field(line.strip())
                if nested is not None:
                    with_fields[nested[0]] = nested[1]
                continue
            if section == "run" and indent > top_indent:
                run_lines.append(line.strip())
            elif indent <= top_indent and line.strip():
                section = None
        name = fields.get("name") or None
        parsed.append(
            WorkflowStep(
                job=job,
                start=start,
                end=end,
                item_indent=item_indent,
                name=name,
                job_fields=job_fields[job],
                fields=fields,
                with_fields=with_fields,
                run_lines=run_lines,
            )
        )
    return parsed


def validate_workflow(root: Path) -> None:
    path = root / ".github/workflows/build.yml"
    value = read_utf8(path)
    lines = active_workflow_lines(value)
    active = "\n".join(lines)
    forbidden_workflow_fields = workflow_top_level_fields(lines) & {
        "<<",
        "defaults",
        "env",
    }
    if forbidden_workflow_fields:
        raise ValidationError(
            f"{path}: forbidden workflow-level fields: "
            f"{sorted(forbidden_workflow_fields)}"
        )
    job_names = workflow_job_names(lines)
    steps = workflow_steps(lines)
    required_names = (
        "Validate GRVMgram sources",
        "Fetch submodules by exact commit",
        "Collect IPA",
        "Validate GRVMgram IPA",
        "Upload IPA",
        "Upload build log",
    )
    named_steps: dict[str, WorkflowStep] = {}
    for step in steps:
        if step.name in required_names:
            if step.name in named_steps:
                raise ValidationError(f"{path}: duplicate workflow step {step.name}")
            named_steps[step.name] = step
    missing = next((name for name in required_names if name not in named_steps), None)
    if missing is not None:
        raise ValidationError(f"{path}: missing workflow step {missing}")

    if len(job_names) != 1:
        raise ValidationError(
            f"{path}: expected exactly one workflow job; required workflow steps "
            "must be in the same job"
        )

    required_steps = [named_steps[name] for name in required_names]
    jobs = {step.job for step in required_steps}
    if len(jobs) != 1 or jobs != {job_names[0]}:
        raise ValidationError(f"{path}: required workflow steps must be in the same job")
    release_job_fields = required_steps[0].job_fields
    approved_job_fields = {"continue-on-error", "if", "runs-on"}
    unexpected_job_fields = set(release_job_fields) - approved_job_fields
    if (
        unexpected_job_fields
        or release_job_fields.get("runs-on") != "macos-26"
        or release_job_fields.get("if") not in {None, "success()"}
        or (
            "continue-on-error" in release_job_fields
            and release_job_fields["continue-on-error"] != "false"
        )
    ):
        raise ValidationError(f"{path}: release job is disabled or non-blocking")

    checkout_steps = [
        step
        for step in steps
        if re.fullmatch(r"actions/checkout@[^\s]+", step.fields.get("uses", ""))
    ]
    if not checkout_steps:
        raise ValidationError(f"{path}: missing actions/checkout step")
    positions = {id(step): index for index, step in enumerate(steps)}
    source = named_steps["Validate GRVMgram sources"]
    fetch = named_steps["Fetch submodules by exact commit"]
    collect = named_steps["Collect IPA"]
    ipa = named_steps["Validate GRVMgram IPA"]
    upload = named_steps["Upload IPA"]
    build_log = named_steps["Upload build log"]
    checkout_candidates = [step for step in checkout_steps if step.job == source.job]
    if not checkout_candidates:
        raise ValidationError(f"{path}: missing actions/checkout step before source gate")
    earlier_checkouts = [
        step
        for step in checkout_candidates
        if positions[id(step)] < positions[id(source)]
    ]
    if not earlier_checkouts:
        raise ValidationError(f"{path}: workflow step order is invalid")
    checkout = earlier_checkouts[-1]
    if (
        checkout.fields != {"uses": "actions/checkout@v4", "with": ""}
        or checkout.with_fields
        != {"submodules": "recursive", "fetch-depth": "0"}
    ):
        raise ValidationError(f"{path}: checkout step contract is incomplete")
    if positions[id(source)] != positions[id(checkout)] + 1:
        raise ValidationError(f"{path}: source gate must run immediately after checkout")
    if positions[id(fetch)] != positions[id(source)] + 1:
        raise ValidationError(f"{path}: source step must be immediately followed by fetch")
    release_gates = (source, fetch, collect, ipa, upload)
    gate_positions = [positions[id(step)] for step in release_gates]
    if gate_positions != sorted(gate_positions):
        raise ValidationError(f"{path}: workflow step order is invalid")
    if (
        positions[id(ipa)] != positions[id(collect)] + 1
        or positions[id(upload)] != positions[id(ipa)] + 1
    ):
        raise ValidationError(
            f"{path}: Collect, Validate, and Upload IPA steps must be adjacent"
        )

    def canonical_run_lines(step: WorkflowStep) -> tuple[str, ...]:
        return tuple(line for line in step.run_lines if line)

    def field_is(step: WorkflowStep, field: str, value: str) -> bool:
        return step.fields.get(field) == value

    def is_hard_failing(step: WorkflowStep) -> bool:
        return step.fields.get("continue-on-error") in {None, "false"}

    def require_step_fields(step: WorkflowStep, allowed: set[str]) -> None:
        unexpected = sorted(set(step.fields) - allowed)
        if unexpected:
            source_label = "; source step is invalid" if step is source else ""
            raise ValidationError(
                f"{path}: {step.name} step has unexpected fields {unexpected}"
                f"{source_label}"
            )

    run_step_fields = {"continue-on-error", "if", "name", "run"}
    action_step_fields = {"continue-on-error", "if", "name", "uses", "with"}
    for step in (source, fetch, collect, ipa):
        require_step_fields(step, run_step_fields)
    for step in (upload, build_log):
        require_step_fields(step, action_step_fields)

    if (
        source.fields.get("run") != "|"
        or canonical_run_lines(source) != SOURCE_RUN_LINES
        or source.fields.get("if") not in {None, "success()"}
        or not is_hard_failing(source)
    ):
        raise ValidationError(f"{path}: source step is incomplete or disabled")
    if (
        fetch.fields.get("run") != "|"
        or canonical_run_lines(fetch) != FETCH_RUN_LINES
        or fetch.fields.get("if") not in {None, "success()"}
        or not is_hard_failing(fetch)
    ):
        raise ValidationError(
            f"{path}: Fetch submodules by exact commit step is incomplete or non-blocking"
        )
    if (
        not field_is(collect, "if", "success()")
        or collect.fields.get("run") != "|"
        or canonical_run_lines(collect) != COLLECT_RUN_LINES
        or not is_hard_failing(collect)
    ):
        raise ValidationError(f"{path}: Collect IPA step is incomplete or non-blocking")
    if (
        not field_is(ipa, "if", "success()")
        or ipa.fields.get("run") != VALIDATE_IPA_COMMAND
        or canonical_run_lines(ipa) != (VALIDATE_IPA_COMMAND,)
        or not is_hard_failing(ipa)
    ):
        raise ValidationError(
            f"{path}: Validate GRVMgram IPA step is incomplete or non-blocking"
        )
    if not all(
        (
            field_is(upload, "if", "success()"),
            upload.fields.get("uses") == "actions/upload-artifact@v4",
            upload.with_fields.get("name") == "GRVMgram-ipa",
            upload.with_fields.get("path") == "artifacts/GRVMgram.ipa",
            upload.with_fields.get("if-no-files-found") == "error",
            set(upload.with_fields) == {"if-no-files-found", "name", "path"},
            is_hard_failing(upload),
        )
    ):
        raise ValidationError(f"{path}: Upload IPA step is incomplete or non-blocking")
    if not all(
        (
            field_is(build_log, "if", "always()"),
            build_log.fields.get("uses") == "actions/upload-artifact@v4",
            build_log.with_fields.get("name") == "build-log",
            build_log.with_fields.get("path") == "build_log.txt",
            build_log.with_fields.get("if-no-files-found") == "warn",
            set(build_log.with_fields) == {"if-no-files-found", "name", "path"},
            is_hard_failing(build_log),
        )
    ):
        raise ValidationError(f"{path}: build log upload contract is incomplete")
    if "name: Telegram-ipa" in active or re.search(r"(?m)^\s*path:\s*artifacts\s*$", active):
        raise ValidationError(f"{path}: legacy public artifact name remains")


def validate_source(root: Path) -> None:
    validate_localizations(root)
    validate_public_branding(root)
    validate_metadata(root)
    validate_workflow(root)


def _zip_member_type(member: zipfile.ZipInfo) -> int:
    return stat.S_IFMT(member.external_attr >> 16)


def _zip_member_is_directory(member: zipfile.ZipInfo) -> bool:
    return (
        member.is_dir()
        or (member.create_system == 3 and _zip_member_type(member) == stat.S_IFDIR)
        or (member.create_system == 0 and bool(member.external_attr & 0x10))
    )


def _require_regular_zip_member(
    archive: zipfile.ZipFile, name: str
) -> zipfile.ZipInfo:
    member = archive.getinfo(name)
    if _zip_member_is_directory(member):
        raise ValidationError(f"IPA member {name!r} must be a regular file")
    return member


def validate_zip_members(archive: zipfile.ZipFile) -> set[str]:
    members = archive.infolist()
    names = [member.filename for member in members]
    if len(names) != len(set(names)):
        raise ValidationError("IPA contains ambiguous duplicate member paths")
    canonical_members: dict[str, tuple[zipfile.ZipInfo, bool, str]] = {}
    for member in members:
        name = member.filename
        unix_type = _zip_member_type(member)
        if member.create_system == 3:
            if unix_type == stat.S_IFLNK:
                raise ValidationError(f"IPA contains symbolic link member: {name!r}")
            if unix_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValidationError(
                    f"IPA contains unsupported Unix file type: {name!r}"
                )
        if not name or name.startswith(("/", "\\")) or "\\" in name:
            raise ValidationError(f"IPA contains unsafe member path: {name!r}")
        if re.match(r"^[A-Za-z]:", name):
            raise ValidationError(f"IPA contains unsafe member path: {name!r}")
        normalized = name.rstrip("/")
        components = normalized.split("/")
        if not normalized or any(component in {"", ".", ".."} for component in components):
            raise ValidationError(f"IPA contains unsafe member path: {name!r}")
        canonical = unicodedata.normalize("NFC", normalized).casefold()
        if canonical in canonical_members:
            raise ValidationError(f"IPA contains ambiguous canonical member path: {name!r}")
        is_directory = _zip_member_is_directory(member)
        root = components[0]
        is_standard_file = (
            len(components) == 1
            and (
                root in IPA_FILE_ROOTS
                or ITUNES_ARTWORK_RE.fullmatch(root) is not None
            )
        )
        if root not in IPA_DIRECTORY_ROOTS and not is_standard_file:
            raise ValidationError(f"IPA contains unsupported IPA root: {root!r}")
        if is_standard_file and is_directory:
            raise ValidationError(f"IPA contains invalid IPA file root: {root!r}")
        canonical_members[canonical] = (member, is_directory, normalized)

    for _canonical, (_member, _is_directory, normalized) in canonical_members.items():
        components = normalized.split("/")
        for length in range(1, len(components)):
            prefix = "/".join(components[:length])
            canonical_prefix = unicodedata.normalize("NFC", prefix).casefold()
            ancestor = canonical_members.get(canonical_prefix)
            if ancestor is not None and not ancestor[1]:
                raise ValidationError(
                    "IPA contains file/directory prefix collision: "
                    f"{ancestor[2]!r} prefixes {normalized!r}"
                )

    for _canonical, (_member, is_directory, normalized) in canonical_members.items():
        if normalized in IPA_DIRECTORY_ROOTS and not is_directory:
            raise ValidationError(
                f"IPA contains invalid IPA directory root: {normalized!r}"
            )
    return set(names)


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
        try:
            bad_member = archive.testzip()
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, zlib.error) as error:
            raise ValidationError(f"IPA archive integrity check failed: {error}") from error
        if bad_member is not None:
            raise ValidationError(f"IPA contains corrupt member: {bad_member}")
        names = validate_zip_members(archive)
        app_roots: set[str] = set()
        for name in names:
            direct = re.fullmatch(r"(Payload/[^/]+\.app)/?", name)
            descendant = re.match(r"^(Payload/[^/]+\.app)/", name)
            if direct is not None:
                app_roots.add(direct.group(1))
            elif descendant is not None:
                app_roots.add(descendant.group(1))
        if len(app_roots) != 1:
            raise ValidationError(
                f"expected exactly one Payload/*.app bundle, got {sorted(app_roots)}"
            )
        app_root = next(iter(app_roots))
        unsupported_payload_members = sorted(
            normalized
            for name in names
            if (normalized := name.rstrip("/")).startswith("Payload/")
            and normalized != app_root
            and not normalized.startswith(f"{app_root}/")
        )
        if unsupported_payload_members:
            raise ValidationError(
                "unsupported Payload member outside main app: "
                f"{unsupported_payload_members}"
            )
        info_path = f"{app_root}/Info.plist"
        if info_path not in names:
            raise ValidationError(f"missing {info_path}")
        _require_regular_zip_member(archive, info_path)
        try:
            info_bytes = archive.read(info_path)
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, zlib.error) as error:
            raise ValidationError(f"IPA archive read failed for {info_path}: {error}") from error
        try:
            info = plistlib.loads(info_bytes)
        except (
            KeyError,
            plistlib.InvalidFileException,
            ValueError,
            expat.ExpatError,
        ) as error:
            raise ValidationError(f"invalid app Info.plist: {error}") from error
        if not isinstance(info, dict):
            raise ValidationError("invalid app Info.plist: expected dictionary")
        if info.get("CFBundleDisplayName") != "GRVMgram":
            raise ValidationError(
                f"CFBundleDisplayName is {info.get('CFBundleDisplayName')!r}"
            )
        if info.get("CFBundleName") != "GRVMgram":
            raise ValidationError(f"CFBundleName is {info.get('CFBundleName')!r}")
        for metadata_key in (
            "CFBundleIdentifier",
            "CFBundleShortVersionString",
            "CFBundleVersion",
        ):
            metadata_value = info.get(metadata_key)
            if not isinstance(metadata_value, str) or not metadata_value.strip():
                raise ValidationError(
                    f"{metadata_key} must be a present, nonempty string"
                )

        executable = info.get("CFBundleExecutable")
        if not isinstance(executable, str) or not executable or "/" in executable:
            raise ValidationError("missing main app executable")
        executable_path = f"{app_root}/{executable}"
        if executable_path not in names:
            raise ValidationError(f"missing main app executable {executable_path!r}")
        executable_info = _require_regular_zip_member(archive, executable_path)
        if executable_info.file_size == 0:
            raise ValidationError("main app executable is empty")

        localized_tables: dict[str, dict[str, str]] = {}
        for language in ("en", "ru"):
            resource_path = f"{app_root}/{language}.lproj/GRVMgram.strings"
            if resource_path not in names:
                raise ValidationError(f"missing IPA resource {resource_path}")
            _require_regular_zip_member(archive, resource_path)
            try:
                resource_text = archive.read(resource_path).decode("utf-8")
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, zlib.error) as error:
                raise ValidationError(
                    f"IPA archive read failed for {resource_path}: {error}"
                ) from error
            except UnicodeDecodeError as error:
                raise ValidationError(
                    f"{resource_path}: not strict UTF-8: {error}"
                ) from error
            localized_tables[language] = parse_strings_text(resource_text, resource_path)
        validate_table_pair(
            localized_tables["en"], localized_tables["ru"], label="IPA localization"
        )
        validate_required_localization_contract(
            localized_tables["en"], localized_tables["ru"]
        )
        expected_keys = validate_localizations(REPOSITORY_ROOT)
        actual_keys = set(localized_tables["en"])
        if actual_keys != expected_keys:
            missing_keys = sorted(expected_keys - actual_keys)
            extra_keys = sorted(actual_keys - expected_keys)
            raise ValidationError(
                "IPA localization inventory mismatch: "
                f"missing_keys={missing_keys}, extra_keys={extra_keys}"
            )

        return {
            "display_name": str(info["CFBundleDisplayName"]),
            "bundle_name": str(info["CFBundleName"]),
            "bundle_id": info["CFBundleIdentifier"],
            "version": info["CFBundleShortVersionString"],
            "build": info["CFBundleVersion"],
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
