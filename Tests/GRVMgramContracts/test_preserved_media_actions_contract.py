import re
import sqlite3
import unittest
from dataclasses import dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def swift_multiline_string(text: str, name: str) -> str:
    anchor = f'static let {name} = """'
    start = text.find(anchor)
    if start < 0:
        return ""
    start += len(anchor)
    end = text.find('"""', start)
    return text[start:end] if end >= 0 else ""


def around(text: str, anchor: str, before: int = 2500, after: int = 2500) -> str:
    start = text.find(anchor)
    if start < 0:
        return ""
    return text[max(0, start - before) : start + len(anchor) + after]


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        return ""
    opening = text.find("{", start)
    if opening < 0:
        return ""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def swift_calls(text: str, signature: str) -> list[str]:
    """Return balanced call expressions so argument ownership can be checked."""
    calls: list[str] = []
    cursor = 0
    while True:
        start = text.find(signature, cursor)
        if start < 0:
            return calls
        opening = text.find("(", start + len(signature))
        if opening < 0:
            return calls
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    calls.append(text[start : index + 1])
                    cursor = index + 1
                    break
        else:
            return calls


def prepared_call_sql(call: str, source_text: str) -> str:
    inline = re.search(r'\bsql\s*:\s*"""(.*?)"""', call, re.DOTALL)
    if inline is not None:
        return inline.group(1)
    single_line = re.search(r'\bsql\s*:\s*"([^"\n]*)"', call)
    if single_line is not None:
        return single_line.group(1)
    named = re.search(r"\bsql\s*:\s*Self\.([A-Za-z_][A-Za-z0-9_]*)", call)
    if named is None:
        return ""
    multiline = swift_multiline_string(source_text, named.group(1))
    if multiline:
        return multiline
    static_line = re.search(
        rf"static\s+let\s+{re.escape(named.group(1))}\s*=\s*\"([^\"\n]*)\"",
        source_text,
    )
    return static_line.group(1) if static_line is not None else ""


def exact_sentinel_delete_call(
    call: str,
    source_text: str,
    *,
    key_expression: str,
    sentinel_name: str,
    resource_expression: str,
) -> bool:
    sql = prepared_call_sql(call, source_text)
    if (
        "DELETE FROM archived_message_media" not in sql
        or re.search(r"\bor\b", sql, re.IGNORECASE)
    ):
        return False
    for predicate in (
        "account_id = ?",
        "peer_id = ?",
        "message_namespace = ?",
        "message_id = ?",
        "thread_id = ?",
        "revision_id = ?",
        "resource_id = ?",
    ):
        if sql.count(predicate) != 1:
            return False
    values = normalized_swift_expression(
        swift_top_level_argument(call, "values")
    )
    values = re.sub(r"\bSelf\.", "", values)
    key = normalized_swift_expression(key_expression)
    resource = normalized_swift_expression(resource_expression)
    expected = (
        f"keyValues({key})+"
        f"[.int64({sentinel_name}),.text({resource})]"
    )
    return values == expected


def action_item_containing(text: str, *anchors: str) -> tuple[str, str]:
    """Find a menu item by behavior, so labels may come from any locale."""
    for item in swift_calls(text, "ContextMenuActionItem"):
        if all(anchor in item for anchor in anchors):
            return item, swift_block(item, "action: {")
    return "", ""


def swift_top_level_argument(call: str, label: str) -> str:
    opening = call.find("(")
    if opening < 0:
        return ""
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    index = opening
    while index < len(call):
        character = call[index]
        if call.startswith("//", index):
            newline = call.find("\n", index + 2)
            index = len(call) if newline < 0 else newline + 1
            continue
        if call.startswith("/*", index):
            closing = call.find("*/", index + 2)
            index = len(call) if closing < 0 else closing + 2
            continue
        if call.startswith('"""', index):
            closing = call.find('"""', index + 3)
            index = len(call) if closing < 0 else closing + 3
            continue
        if character == '"':
            index += 1
            while index < len(call):
                if call[index] == "\\":
                    index += 2
                    continue
                if call[index] == '"':
                    index += 1
                    break
                index += 1
            continue
        if character == "(":
            paren_depth += 1
        elif character == ")":
            if paren_depth == 1 and brace_depth == 0 and bracket_depth == 0:
                return ""
            paren_depth -= 1
        elif character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth -= 1
        elif character == "[":
            bracket_depth += 1
        elif character == "]":
            bracket_depth -= 1
        elif paren_depth == 1 and brace_depth == 0 and bracket_depth == 0:
            label_match = re.match(rf"{re.escape(label)}\s*:\s*", call[index:])
            if label_match is not None:
                start = index + label_match.end()
                cursor = start
                nested_parens = 1
                nested_braces = 0
                nested_brackets = 0
                while cursor < len(call):
                    if call.startswith("//", cursor):
                        newline = call.find("\n", cursor + 2)
                        cursor = len(call) if newline < 0 else newline + 1
                        continue
                    if call.startswith("/*", cursor):
                        closing = call.find("*/", cursor + 2)
                        cursor = len(call) if closing < 0 else closing + 2
                        continue
                    if call.startswith('"""', cursor):
                        closing = call.find('"""', cursor + 3)
                        cursor = len(call) if closing < 0 else closing + 3
                        continue
                    current = call[cursor]
                    if current == '"':
                        cursor += 1
                        while cursor < len(call):
                            if call[cursor] == "\\":
                                cursor += 2
                                continue
                            if call[cursor] == '"':
                                cursor += 1
                                break
                            cursor += 1
                        continue
                    if current == "(":
                        nested_parens += 1
                    elif current == ")":
                        nested_parens -= 1
                        if nested_parens == 0 and nested_braces == 0 and nested_brackets == 0:
                            return call[start:cursor].strip()
                    elif current == "{":
                        nested_braces += 1
                    elif current == "}":
                        nested_braces -= 1
                    elif current == "[":
                        nested_brackets += 1
                    elif current == "]":
                        nested_brackets -= 1
                    elif (
                        current == ","
                        and nested_parens == 1
                        and nested_braces == 0
                        and nested_brackets == 0
                    ):
                        return call[start:cursor].strip()
                    cursor += 1
                return call[start:].strip()
        index += 1
    return ""


def swift_block_at(text: str, start: int) -> tuple[str, int]:
    """Return a brace-balanced block and its end offset from an existing match."""
    opening = text.find("{", start)
    if opening < 0:
        return "", -1
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1
    return text[start:], len(text)


def strip_balanced_outer_parentheses(expression: str) -> str:
    result = expression.strip()
    while result.startswith("(") and result.endswith(")"):
        depth = 0
        encloses_all = True
        for index, character in enumerate(result):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and index != len(result) - 1:
                    encloses_all = False
                    break
        if not encloses_all or depth != 0:
            break
        result = result[1:-1].strip()
    return result


def normalized_swift_expression(expression: str) -> str:
    result = swift_without_comments(expression).strip()
    result = re.sub(r"\belse\s*$", "", result).strip()
    result = strip_balanced_outer_parentheses(result)
    result = re.sub(r"\bself\.", "", result)
    return re.sub(r"\s+", "", result)


def exact_boolean_polarity(expression: str, variable: str) -> bool | None:
    normalized = normalized_swift_expression(expression)
    positive = {
        variable,
        f"{variable}==true",
        f"true=={variable}",
    }
    negative = {
        f"!{variable}",
        f"{variable}==false",
        f"false=={variable}",
    }
    if normalized in positive:
        return True
    if normalized in negative:
        return False
    return None


def is_exact_view_once_expression(expression: str) -> bool:
    normalized = normalized_swift_expression(expression)
    return re.fullmatch(
        r"consumeViewOnce&&(?:timeout|(?:[A-Za-z_]\w*\.)*"
        r"minAutoremoveOrClearTimeout)==viewOnceTimeout",
        normalized,
    ) is not None


def resolve_swift_boolean_alias(
    text: str,
    expression: str,
    *,
    before: int | None = None,
) -> str:
    candidate = strip_balanced_outer_parentheses(expression.strip())
    candidate = re.sub(r"^self\.", "", candidate)
    if re.fullmatch(r"[A-Za-z_]\w*", candidate) is None:
        return expression
    scope = text if before is None else text[:before]
    assignments = list(
        re.finditer(
            rf"(?:let|var)\s+{re.escape(candidate)}\s*=\s*(?P<value>[^\n;]+)",
            scope,
        )
    )
    return assignments[-1].group("value").strip() if assignments else expression


def is_exact_receipt_expression(expression: str) -> bool:
    normalized = normalized_swift_expression(expression)
    return re.fullmatch(
        r"consumeViewOnce\|\|(?:timeout|(?:[A-Za-z_]\w*\.)*"
        r"minAutoremoveOrClearTimeout)!=viewOnceTimeout",
        normalized,
    ) is not None


def is_exact_receipt_suppression_expression(expression: str) -> bool:
    normalized = normalized_swift_expression(expression)
    return re.fullmatch(
        r"!consumeViewOnce&&(?:timeout|(?:[A-Za-z_]\w*\.)*"
        r"minAutoremoveOrClearTimeout)==viewOnceTimeout",
        normalized,
    ) is not None


def call_is_owned_by_exact_receipt_gate(text: str, signature: str) -> bool:
    call_position = text.find(signature)
    if call_position < 0:
        return False
    for match in re.finditer(
        r"\b(?P<kind>if|guard)\s+(?P<condition>[^\{\n]+)\{",
        text,
    ):
        block, end = swift_block_at(text, match.start())
        if not block:
            continue
        condition = match.group("condition")
        kind = match.group("kind")
        if kind == "if" and is_exact_receipt_expression(condition):
            if (
                match.start() <= call_position < end
                and not position_is_enclosed_by_other_if(
                    text,
                    call_position,
                    allowed_start=match.start(),
                    ignore_playlist_item_type_bindings=True,
                )
            ):
                return True
        if kind == "if" and is_exact_receipt_suppression_expression(condition):
            if (
                block_has_top_level_return(block)
                and end <= call_position
                and not position_is_enclosed_by_other_if(
                    text,
                    call_position,
                    ignore_playlist_item_type_bindings=True,
                )
            ):
                return True
        if kind == "guard" and is_exact_receipt_expression(condition):
            if (
                block_has_top_level_return(block)
                and end <= call_position
                and not position_is_enclosed_by_other_if(
                    text,
                    call_position,
                    ignore_playlist_item_type_bindings=True,
                )
            ):
                return True
    return False


def burn_confirmation_ignores_prepare_bool(confirmation: str) -> bool:
    prepare_calls = swift_calls(confirmation, "prepareConsumableMedia")
    forced_calls = [
        call
        for call in swift_calls(
            confirmation,
            "markMessageContentAsConsumedInteractively",
        )
        if re.search(r"\bforce\s*:\s*true\b", call)
    ]
    if len(prepare_calls) != 1 or len(forced_calls) != 1:
        return False
    prepare_position = confirmation.find(prepare_calls[0])
    force_position = confirmation.find(forced_calls[0], prepare_position + len(prepare_calls[0]))
    if prepare_position < 0 or force_position < 0:
        return False
    between = confirmation[prepare_position + len(prepare_calls[0]) : force_position]
    if re.search(r"\b(?:filter|compactMap)\b|\b(?:if|guard)\b", between):
        return False
    ignored_callback = re.search(
        r"\|>\s*(?:map|mapToSignal)\s*\{\s*_\s+in\b",
        between,
    )
    ignored_values = re.search(
        r"\|>\s*ignoreValues\s*\|>\s*then\s*\(",
        between,
    )
    ignored_next = re.search(
        r"\.start(?:Standalone)?\s*\([^)]*\bnext\s*:\s*\{\s*_\s+in\b",
        between,
        re.DOTALL,
    )
    return any((ignored_callback, ignored_values, ignored_next))


def replay_fresh_row_fail_closed(text: str) -> str:
    binding = re.search(
        r"guard\s+let\s+(?P<row>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
        r"transaction\.getMessage\(message\.id\)\s+else\s*\{",
        text,
    )
    if binding is None:
        return ""
    failure_block, _ = swift_block_at(text, binding.start())
    if not failure_block:
        return ""
    body = swift_top_level_block_body(failure_block)
    if re.search(r"\breturn\b", body) is None:
        return ""
    if re.search(r"(?:present|displayUndo|textAlertController)", body) is None:
        return ""
    if "openMessage" in failure_block:
        return ""
    return binding.group("row")


def swift_top_level_block_body(block: str) -> str:
    opening = block.find("{")
    if opening < 0:
        return ""
    depth = 1
    result: list[str] = []
    index = opening + 1
    while index < len(block) and depth > 0:
        character = block[index]
        if character == "{":
            depth += 1
            result.append(" ")
        elif character == "}":
            depth -= 1
            if depth > 0:
                result.append(" ")
        elif depth == 1:
            result.append(character)
        else:
            result.append(" ")
        index += 1
    return "".join(result)


def block_has_top_level_return(block: str) -> bool:
    return re.search(r"\breturn\b", swift_top_level_block_body(block)) is not None


def block_has_unconditional_result(block: str, value: bool) -> bool:
    body = swift_top_level_block_body(block)
    literal = "true" if value else "false"
    return re.search(
        rf"(?:\breturn\s+{literal}\b|\.single\(\s*{literal}\s*\)|"
        rf"putNext\(\s*{literal}\s*\))",
        body,
    ) is not None


def position_is_enclosed_by_other_if(
    text: str,
    position: int,
    *,
    allowed_start: int | None = None,
    ignore_playlist_item_type_bindings: bool = False,
) -> bool:
    for match in re.finditer(r"\bif\b", text):
        if match.start() >= position:
            break
        if match.start() == allowed_start:
            continue
        block, end = swift_block_at(text, match.start())
        opening = text.find("{", match.start())
        if ignore_playlist_item_type_bindings and opening >= 0:
            condition = text[match.end() : opening].strip()
            if re.fullmatch(
                r"(?:let|var)\s+[A-Za-z_]\w*\s*=\s*[^,]+\s+as\?\s+"
                r"MessageMediaPlaylistItem",
                condition,
            ):
                continue
        if block and opening < position < end:
            return True
    return False


def prepare_fresh_row_stable_id_fail_closed(text: str) -> str:
    binding = re.search(
        r"(?:guard\s+let|if\s+let|let)\s+(?P<row>[A-Za-z_]\w*)\s*=\s*"
        r"transaction\.getMessage\(message\.id\)",
        text,
    )
    if binding is None:
        return ""
    row = binding.group("row")
    boundary_candidates = [
        position
        for anchor in (
            "completedResourcePath",
            "reserveConsumableMedia(",
            "mediaStore.archive(",
            "store.updateMedia(",
            "GRVMPreservedConsumableMediaAttribute(",
        )
        if (position := text.find(anchor, binding.end())) >= 0
    ]
    boundary = min(boundary_candidates, default=len(text))
    prefix = text[binding.start() : boundary]
    equality = {
        f"{row}.stableId==message.stableId",
        f"message.stableId=={row}.stableId",
    }
    mismatch = {
        f"{row}.stableId!=message.stableId",
        f"message.stableId!={row}.stableId",
    }
    for guard_match in re.finditer(
        r"\bguard\s+(?P<condition>.*?)\s+else\s*\{",
        prefix,
        re.DOTALL,
    ):
        condition = normalized_swift_expression(guard_match.group("condition"))
        exact_gate = condition in equality
        combined_gate = (
            condition.startswith(f"let{row}=transaction.getMessage(message.id),")
            and condition.rsplit(",", 1)[-1] in equality
            and "||" not in condition
        )
        if not (exact_gate or combined_gate):
            continue
        absolute_start = binding.start() + guard_match.start()
        if position_is_enclosed_by_other_if(text, absolute_start):
            continue
        failure_block, _ = swift_block_at(prefix, guard_match.start())
        if block_has_unconditional_result(failure_block, False):
            return row
    for if_match in re.finditer(
        r"\bif\s+(?P<condition>[^\{\n]+)\{",
        prefix,
    ):
        if normalized_swift_expression(if_match.group("condition")) not in mismatch:
            continue
        absolute_start = binding.start() + if_match.start()
        if position_is_enclosed_by_other_if(text, absolute_start):
            continue
        failure_block, _ = swift_block_at(prefix, if_match.start())
        if block_has_unconditional_result(failure_block, False):
            return row
    return ""


def prepare_positive_marker_idempotent_success(text: str, row: str) -> bool:
    binding_position = text.find(f"transaction.getMessage(message.id)")
    if binding_position < 0:
        return False
    boundary_candidates = [
        position
        for anchor in (
            "completedResourcePath",
            "reserveConsumableMedia(",
            "mediaStore.archive(",
            "store.updateMedia(",
        )
        if (position := text.find(anchor, binding_position)) >= 0
    ]
    boundary = min(boundary_candidates, default=len(text))
    prefix = text[binding_position:boundary]
    positive_pattern = re.compile(
        rf"\bif\s+{re.escape(row)}\.attributes\.contains\s*\(\s*where\s*:\s*"
        r"\{\s*\$0\s+is\s+GRVMPreservedConsumableMediaAttribute\s*\}\s*\)\s*\{"
    )
    positive_ranges: list[tuple[int, int]] = []
    for match in positive_pattern.finditer(prefix):
        if position_is_enclosed_by_other_if(
            text,
            binding_position + match.start(),
        ):
            continue
        block, end = swift_block_at(prefix, match.end() - 1)
        if block and block_has_unconditional_result(block, True):
            positive_ranges.append((match.start(), end))
    success_positions = [
        match.start()
        for match in re.finditer(
            r"(?:\breturn\s+true\b|\.single\(\s*true\s*\)|"
            r"putNext\(\s*true\s*\))",
            prefix,
        )
    ]
    return bool(success_positions) and all(
        any(start <= position < end for start, end in positive_ranges)
        for position in success_positions
    )


def failure_block_rolls_back_before_false(block: str) -> bool:
    body = swift_top_level_block_body(block)
    rollback_position = body.find("rollbackConsumableMediaReservation")
    false_result = re.search(
        r"(?:\breturn\s+false\b|\.single\(\s*false\s*\)|"
        r"putNext\(\s*false\s*\))",
        body,
    )
    return (
        rollback_position >= 0
        and false_result is not None
        and rollback_position < false_result.start()
    )


def prepare_terminal_marker_fail_closed(text: str) -> bool:
    marker_position = text.rfind("GRVMPreservedConsumableMediaAttribute(")
    if marker_position < 0:
        return False
    required_binding = re.search(
        r"(?:let|var)\s+(?P<required>[A-Za-z_]\w*(?:primary|required)\w*Ids)\s*=",
        text[:marker_position],
        re.IGNORECASE,
    )
    terminal_validation = re.search(
        r"(?s)\b(?P<records>[A-Za-z_]\w*)\.(?:allSatisfy|all)\s*"
        r"(?:\(\s*)?\{.*?\.complete.*?(?:byteCount|size)\s*>\s*0",
        text[:marker_position],
    )
    if required_binding is None or terminal_validation is None:
        return False
    required_ids = required_binding.group("required")
    records = terminal_validation.group("records")
    terminal_ids = set(
        re.findall(
            rf"(?s)(?:let|var)\s+([A-Za-z_]\w*)\s*=\s*"
            rf"{re.escape(records)}\.(?:map|compactMap).*?resourceId.*?\.sorted\(\)",
            text[:marker_position],
        )
    )
    if not terminal_ids:
        return False

    completeness_aliases: set[str] = set()
    for match in re.finditer(
        rf"(?:let|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*"
        rf"{re.escape(records)}\.(?:allSatisfy|all)\s*\{{",
        text[:marker_position],
    ):
        assignment, _ = swift_block_at(text[:marker_position], match.start())
        if (
            ".complete" in assignment
            and re.search(r"(?:byteCount|size)\s*>\s*0", assignment)
        ):
            completeness_aliases.add(match.group("name"))

    equality_aliases: set[str] = set()
    equality_patterns = []
    for terminal_name in terminal_ids:
        equality_patterns.extend(
            (
                f"Set({required_ids})==Set({terminal_name})",
                f"Set({terminal_name})==Set({required_ids})",
            )
        )
    for assignment in re.finditer(
        r"(?:let|var)\s+(?P<name>[A-Za-z_]\w*)\s*=\s*(?P<expression>[^\n]+)",
        text[:marker_position],
    ):
        if normalized_swift_expression(assignment.group("expression")) in equality_patterns:
            equality_aliases.add(assignment.group("name"))
    if not completeness_aliases or not equality_aliases:
        return False

    covered_complete = False
    covered_equality = False
    prefix = text[:marker_position]
    for guard_match in re.finditer(
        r"\bguard\s+(?P<condition>.*?)\s+else\s*\{",
        prefix,
        re.DOTALL,
    ):
        condition = guard_match.group("condition")
        normalized = normalized_swift_expression(condition)
        if "||" in normalized:
            continue
        owns_complete = any(
            re.search(rf"\b{re.escape(alias)}\b", condition)
            for alias in completeness_aliases
        )
        owns_equality = any(
            re.search(rf"\b{re.escape(alias)}\b", condition)
            for alias in equality_aliases
        )
        if not (owns_complete or owns_equality):
            continue
        if position_is_enclosed_by_other_if(text, guard_match.start()):
            continue
        failure_block, _ = swift_block_at(prefix, guard_match.start())
        if not failure_block_rolls_back_before_false(failure_block):
            return False
        covered_complete = covered_complete or owns_complete
        covered_equality = covered_equality or owns_equality
    if covered_complete and covered_equality:
        return True

    for if_match in re.finditer(
        r"\bif\s+(?P<condition>[^\{\n]+)\{",
        text,
    ):
        condition = if_match.group("condition")
        normalized = normalized_swift_expression(condition)
        if "||" in normalized:
            continue
        owns_complete = any(
            re.search(rf"\b{re.escape(alias)}\b", condition)
            for alias in completeness_aliases
        )
        owns_equality = any(
            re.search(rf"\b{re.escape(alias)}\b", condition)
            for alias in equality_aliases
        )
        if not (owns_complete and owns_equality):
            continue
        if position_is_enclosed_by_other_if(text, if_match.start()):
            continue
        success_block, end = swift_block_at(text, if_match.start())
        if not (if_match.start() <= marker_position < end):
            continue
        else_match = re.match(r"\s*else\s*\{", text[end:])
        if else_match is None:
            continue
        failure_block, _ = swift_block_at(text, end + else_match.start())
        if failure_block_rolls_back_before_false(failure_block):
            return True
    return False


def local_copy_temp_cleanup_is_fail_closed(text: str, temp_name: str) -> bool:
    temp_binding = re.search(
        rf"(?:let|var)\s+{re.escape(temp_name)}\s*=\s*"
        r"FileManager\.default\.temporaryDirectory",
        text,
    )
    if temp_binding is None:
        return False
    handoff_position = text.find(".standalone(media:", temp_binding.end())
    if handoff_position < 0:
        return False
    region = text[temp_binding.start() : handoff_position]
    cleanup_pattern = re.compile(
        rf"(?:removeItem\s*\(\s*at\s*:\s*{re.escape(temp_name)}\b|"
        rf"removeItem\s*\(\s*atPath\s*:\s*{re.escape(temp_name)}\.path\b|"
        rf"unlink\s*\(\s*{re.escape(temp_name)}\.path\b)"
    )
    failure_exit_pattern = re.compile(
        r"(?:putError\s*\(|\bthrow\b|"
        r"\breturn\s+(?:nil|false|\.fail\b))"
    )
    failure_ranges: list[tuple[int, int]] = []
    for catch_match in re.finditer(r"\bcatch(?:\s+[^\{\n]+)?\s*\{", region):
        block, end = swift_block_at(region, catch_match.start())
        if not block:
            continue
        if cleanup_pattern.search(block) is None:
            return False
        top_level = swift_top_level_block_body(block)
        recovers_with_copy = "copyItem(" in top_level or "linkItem(" in top_level
        exits_at_top_level = failure_exit_pattern.search(top_level) is not None
        if exits_at_top_level and cleanup_pattern.search(top_level) is None:
            return False
        if recovers_with_copy and not exits_at_top_level and cleanup_pattern.search(top_level):
            return False
        failure_ranges.append((catch_match.start(), end))
    for branch_match in re.finditer(
        r"\b(?:guard\s+.*?\s+else|if\s+[^\{\n]+)\s*\{",
        region,
        re.DOTALL,
    ):
        block, end = swift_block_at(region, branch_match.start())
        if not block:
            continue
        top_level = swift_top_level_block_body(block)
        if failure_exit_pattern.search(top_level) is None:
            continue
        if cleanup_pattern.search(top_level) is None:
            return False
        failure_ranges.append((branch_match.start(), end))
    cleanup_positions = [match.start() for match in cleanup_pattern.finditer(region)]
    if not failure_ranges or not cleanup_positions:
        return False
    return all(
        any(start <= position < end for start, end in failure_ranges)
        for position in cleanup_positions
    )


def message_attributes_are_allowlist_only(text: str, message_call: str) -> bool:
    attributes_expression = normalized_swift_expression(
        swift_top_level_argument(message_call, "attributes")
    )
    if re.fullmatch(r"[A-Za-z_]\w*", attributes_expression) is None:
        return False
    call_position = text.find(message_call)
    if call_position < 0:
        return False
    declaration_pattern = re.compile(
        rf"\bvar\s+{re.escape(attributes_expression)}\s*:\s*"
        r"\[MessageAttribute\]\s*=\s*\[\]"
    )
    declarations = list(declaration_pattern.finditer(text[:call_position]))
    if not declarations:
        return False
    declaration = declarations[-1]
    flow = text[declaration.end() : call_position]
    if "message.attributes" in flow:
        return False
    if re.search(rf"\b{re.escape(attributes_expression)}\s*\+=", flow):
        return False
    if re.search(rf"\b{re.escape(attributes_expression)}\s*=", flow):
        return False
    if re.search(rf"&\s*{re.escape(attributes_expression)}\b", flow):
        return False
    member_calls = list(
        re.finditer(
            rf"\b{re.escape(attributes_expression)}\."
            r"(?P<method>[A-Za-z_]\w*)\s*\(",
            flow,
        )
    )
    if any(match.group("method") != "append" for match in member_calls):
        return False
    if re.search(rf"\b{re.escape(attributes_expression)}\s*\[", flow):
        return False
    append_calls = swift_calls(flow, f"{attributes_expression}.append")
    if len(append_calls) != len(member_calls):
        return False
    for append_call in append_calls:
        opening = append_call.find("(")
        argument = append_call[opening + 1 : -1].strip()
        if re.fullmatch(
            r"TextEntitiesMessageAttribute\s*\(.*\)",
            argument,
            re.DOTALL,
        ) is None:
            return False
    for forbidden_attribute in (
        "AutoremoveTimeoutMessageAttribute",
        "AutoclearTimeoutMessageAttribute",
        "ConsumableContentMessageAttribute",
        "ReplyMarkupMessageAttribute",
        "ForwardSourceInfoAttribute",
        "SourceReferenceMessageAttribute",
        "ReplyMessageAttribute",
    ):
        if forbidden_attribute in flow:
            return False
    return True


def swift_exact_positive_if_blocks(text: str, variable: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(r"\bif\s+(?P<condition>[^\{\n]+)\{")
    for match in pattern.finditer(text):
        if exact_boolean_polarity(match.group("condition"), variable) is not True:
            continue
        block, _ = swift_block_at(text, match.start())
        if block:
            blocks.append(block)
    return blocks


def swift_condition_ranges(text: str, variable: str) -> list[tuple[int, int]]:
    """Collect only branches owned by an exact durable-marker-negative gate."""
    ranges: list[tuple[int, int]] = []
    condition_pattern = re.compile(
        r"\b(?P<kind>if|guard)\s+(?P<condition>[^\{\n]+)\{"
    )
    for match in condition_pattern.finditer(text):
        polarity = exact_boolean_polarity(match.group("condition"), variable)
        if polarity is None:
            continue
        block, end = swift_block_at(text, match.start())
        if not block:
            continue
        if match.group("kind") == "if" and polarity is False:
            ranges.append((match.start(), end))
        elif match.group("kind") == "if" and polarity is True:
            else_match = re.match(r"\s*else\s*\{", text[end:])
            if else_match:
                _, else_end = swift_block_at(text, end + else_match.start())
                ranges.append((end + else_match.start(), else_end))
        elif match.group("kind") == "guard" and polarity is True:
            ranges.append((match.start(), end))
    return ranges


def occurrence_positions(text: str, needle: str) -> list[int]:
    return [match.start() for match in re.finditer(re.escape(needle), text)]


def all_occurrences_in_ranges(text: str, needle: str, ranges: list[tuple[int, int]]) -> bool:
    positions = occurrence_positions(text, needle)
    return bool(positions) and all(
        any(start <= position < end for start, end in ranges) for position in positions
    )


def swift_without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def switch_case(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        return ""
    remainder = text[start + len(signature) :]
    next_case = re.search(r"\n\s*(?:case\b|default:)", remainder)
    end = len(text) if next_case is None else start + len(signature) + next_case.start()
    return text[start:end]


def ordered(text: str, *anchors: str) -> bool:
    positions = [text.find(anchor) for anchor in anchors]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


@dataclass(frozen=True)
class BurnCase:
    count: int = 1
    peer: str = "user"
    namespace: str = "cloud"
    incoming: bool = True
    media: str = "image"
    ttl: bool = True
    has_consumable: bool = True
    consumed: bool = False


def burn_eligible(case: BurnCase) -> bool:
    return (
        case.count == 1
        and case.peer in {"user", "group", "channel"}
        and case.namespace == "cloud"
        and case.incoming
        and case.media in {"image", "file"}
        and case.ttl
        and case.has_consumable
        and not case.consumed
    )


def burn_execution_steps(prepared: bool) -> tuple[str, str]:
    preparation = "prepare:complete" if prepared else "prepare:failed"
    return preparation, "consume:force"


def burn_execution_events(
    *, eligible: bool, confirmed: bool, prepared: bool, account: str, message_id: str
) -> tuple[tuple[str, str, str], ...]:
    if not eligible or not confirmed:
        return ()
    return (
        ("prepare", account, message_id),
        ("consume:force", account, message_id),
    )


@dataclass(frozen=True)
class ReplayCase:
    count: int = 1
    has_marker: bool = True
    consumed: bool = True
    expired: bool = False
    locally_deleted: bool = False
    restored: bool = True


def replay_eligible(case: ReplayCase) -> bool:
    lifecycle_allows_replay = case.consumed or case.expired or case.locally_deleted
    return case.count == 1 and case.has_marker and lifecycle_allows_replay and case.restored


def replay_ui_outcome(
    *, eligibility_restore: bool, tap_restore: bool, fresh_row: bool
) -> str:
    if not eligibility_restore:
        return "hidden"
    if not tap_restore or not fresh_row:
        return "unavailable-alert"
    return "open-fresh-without-consume"


@dataclass(frozen=True)
class LocalCopyCase:
    count: int = 1
    deleted: bool = False
    ttl: bool = False
    one_play: bool = False
    source_protected: bool = False
    chat_protected: bool = False
    text: str = ""
    media: tuple[str, ...] = ()
    current_size: int = 0
    restored_size: int = 0


def local_copy_outcome(case: LocalCopyCase) -> str:
    special = any(
        (
            case.deleted,
            case.ttl,
            case.one_play,
            case.source_protected,
            case.chat_protected,
        )
    )
    if case.count != 1 or not special:
        return "notCandidate"
    if not case.media:
        return "ready" if case.text else "unsupported"
    if case.media not in {("image",), ("file",)}:
        return "unsupported"
    return "ready" if max(case.current_size, case.restored_size) > 0 else "unavailable"


def local_copy_temp_cleanup(events: tuple[str, ...]) -> str:
    """The producer cleans failed temp files; a returned resource transfers ownership."""
    if "return-resource" in events:
        return "stock-move-owns-cleanup"
    if "temp-created" in events and "error" in events:
        return "producer-removes-temp"
    return "no-temp"


SAFE_ENTITIES = {
    "Mention",
    "Hashtag",
    "BotCommand",
    "Url",
    "Email",
    "Bold",
    "Italic",
    "Code",
    "Pre",
    "TextUrl",
    "TextMention",
    "PhoneNumber",
    "Strikethrough",
    "BlockQuote",
    "Underline",
    "BankCard",
    "Spoiler",
    "FormattedDate",
}

SAFE_FILE_ATTRIBUTES = {
    "FileName",
    "ImageSize",
    "Sticker",
    "Animated",
    "Video",
    "Audio",
}


def safe_entity(entity: tuple[str, int, int], utf16_length: int) -> bool:
    kind, start, end = entity
    return 0 <= start < end <= utf16_length and kind in SAFE_ENTITIES


def safe_file_attributes(attributes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(attribute for attribute in attributes if attribute in SAFE_FILE_ATTRIBUTES)


def replay_flow(consume_on_open: bool) -> dict[str, bool]:
    return {
        "interaction": consume_on_open,
        "open_chat": consume_on_open,
        "gallery_data": consume_on_open,
        "secret_preview": consume_on_open,
        "playlist": consume_on_open,
        "playback_is_view_once": consume_on_open,
        "prepare": consume_on_open,
        "consume": consume_on_open,
    }


def should_consume_playback(*, consume_view_once: bool, is_view_once: bool) -> bool:
    return consume_view_once or not is_view_once


def decode_force(payload: dict[str, int]) -> bool:
    return payload.get("f", 0) != 0


def sends_content_read(*, suppressed: bool, force: bool) -> bool:
    return force or not suppressed


def merged_media(*, marker: bool, incoming: str) -> tuple[bool, str]:
    media = "preserved" if marker and incoming == "expired" else incoming
    return marker, media


def autoremove_outcome(
    *,
    secret: bool,
    is_remove: bool,
    marker: bool,
    legacy: bool = False,
    ghost: bool = False,
) -> str:
    _ = legacy, ghost
    if secret or is_remove:
        return "delete"
    return "retain-clear-timer" if marker else "expire-clear-timer"


def primary_resource_ids(records: list[tuple[str, int]]) -> tuple[str, ...] | None:
    if not records or any(size <= 0 for _, size in records):
        return None
    return tuple(sorted({resource_id for resource_id, _ in records}))


@dataclass(frozen=True)
class ArchivedMediaRecord:
    account: str
    message_key: str
    resource_id: str
    complete: bool = True
    byte_count: int = 1
    restored_size: int = 1


def terminal_set_authorized(
    *,
    required_ids: tuple[str, ...],
    account: str,
    message_key: str,
    records: tuple[ArchivedMediaRecord, ...],
) -> bool:
    actual_ids = tuple(record.resource_id for record in records)
    return (
        bool(required_ids)
        and len(actual_ids) == len(set(actual_ids))
        and set(actual_ids) == set(required_ids)
        and all(
            record.account == account
            and record.message_key == message_key
            and record.complete
            and record.byte_count > 0
            for record in records
        )
    )


def prepare_terminal_outcome(
    records: tuple[ArchivedMediaRecord, ...],
    required_ids: tuple[str, ...] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    expected = required_ids or tuple(record.resource_id for record in records)
    complete = terminal_set_authorized(
        required_ids=expected,
        account=records[0].account if records else "",
        message_key=records[0].message_key if records else "",
        records=records,
    )
    rollback_ids = () if complete else tuple(record.resource_id for record in records)
    return complete, rollback_ids


def prepare_event_trace(*, existing_marker: bool, terminal_valid: bool) -> tuple[str, ...]:
    events = ["reread"]
    if existing_marker:
        return tuple(events + ["return-success"])
    events += ["probe", "reserve", "archive", "persist-terminal"]
    return tuple(events + (["attach-marker"] if terminal_valid else ["rollback", "return-false"]))


def rollback_attempt_resources(
    *, inserted_resource_ids: tuple[str, ...], terminal_outcome: str
) -> tuple[str, ...]:
    """Only the current reservation's inserted IDs may be rolled back on failure."""
    if terminal_outcome == "markerAttached":
        return ()
    return tuple(sorted(set(inserted_resource_ids)))


def restore_authorized(
    *,
    account: str,
    message_key: str,
    marker_ids: tuple[str, ...],
    records: tuple[ArchivedMediaRecord, ...],
) -> bool:
    expected = set(marker_ids)
    actual = {record.resource_id for record in records}
    return (
        bool(expected)
        and len(records) == len(actual)
        and actual == expected
        and all(
            record.account == account
            and record.message_key == message_key
            and record.complete
            and record.byte_count > 0
            and record.restored_size > 0
            for record in records
        )
    )


def sqlite_sentinel_fixture() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        swift_multiline_string(
            source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"),
            "schemaV2",
        )
    )
    return connection


class SourceContractTestCase(unittest.TestCase):
    def assertContains(self, text: str, anchor: str) -> None:
        if anchor not in text:
            self.fail(f"Missing source anchor: {anchor!r}")

    def assertContainsAll(self, text: str, *anchors: str) -> None:
        for anchor in anchors:
            self.assertContains(text, anchor)

    def assertNotContains(self, text: str, anchor: str) -> None:
        if anchor in text:
            self.fail(f"Forbidden source anchor present: {anchor!r}")

    def assertAnyContains(self, text: str, *anchors: str) -> None:
        if not any(anchor in text for anchor in anchors):
            self.fail(f"Missing one of source anchors: {anchors!r}")

    def assertMatches(self, text: str, pattern: str) -> None:
        if re.search(pattern, text) is None:
            self.fail(f"Missing source pattern: {pattern!r}")

    def assertOrdered(self, text: str, *anchors: str) -> None:
        self.assertTrue(ordered(text, *anchors), msg=f"Expected ordered anchors: {anchors}")


class HardeningMutantRegressionTests(SourceContractTestCase):
    def test_marker_authority_rejects_compound_and_inverted_gates(self) -> None:
        mutants = (
            """
            if !hasMarker || legacyOverride {
                media = [TelegramMediaExpiredContent(data: nil)]
            }
            """,
            """
            if hasMarker && otherFlag {
                retainMedia()
            } else {
                media = [TelegramMediaExpiredContent(data: nil)]
            }
            """,
            """
            if hasMarker == false && legacyOverride {
                media = [TelegramMediaExpiredContent(data: nil)]
            }
            """,
        )
        for mutant in mutants:
            with self.subTest(mutant=mutant.strip().splitlines()[0]):
                self.assertFalse(
                    all_occurrences_in_ranges(
                        mutant,
                        "TelegramMediaExpiredContent",
                        swift_condition_ranges(mutant, "hasMarker"),
                    )
                )
        compound_retained = """
        if hasMarker && otherFlag {
            retainMedia()
        }
        if !hasMarker {
            media = [TelegramMediaExpiredContent(data: nil)]
        }
        """
        self.assertEqual([], swift_exact_positive_if_blocks(compound_retained, "hasMarker"))
        exact = """
        if hasMarker {
            retainMedia()
        } else {
            media = [TelegramMediaExpiredContent(data: nil)]
        }
        """
        self.assertEqual(1, len(swift_exact_positive_if_blocks(exact, "hasMarker")))
        self.assertTrue(
            all_occurrences_in_ranges(
                exact,
                "TelegramMediaExpiredContent",
                swift_condition_ranges(exact, "hasMarker"),
            )
        )

    def test_playlist_polarity_rejects_trailing_logic(self) -> None:
        view_once_mutant = """
        SharedMediaPlaybackDataSource.telegramFile(
            message: message,
            isViewOnce: consumeViewOnce && timeout == viewOnceTimeout || true
        )
        """
        call = swift_calls(
            view_once_mutant,
            "SharedMediaPlaybackDataSource.telegramFile",
        )[0]
        argument = swift_top_level_argument(call, "isViewOnce")
        self.assertFalse(is_exact_view_once_expression(argument))

        receipt_mutant = """
        if consumeViewOnce || timeout != viewOnceTimeout || otherFlag {
            markMessageContentAsConsumedInteractively(messageId: message.id)
        }
        """
        self.assertFalse(
            call_is_owned_by_exact_receipt_gate(
                receipt_mutant,
                "markMessageContentAsConsumedInteractively",
            )
        )
        self.assertTrue(
            is_exact_view_once_expression(
                "consumeViewOnce && timeout == viewOnceTimeout"
            )
        )
        exact_receipt = """
        guard consumeViewOnce || timeout != viewOnceTimeout else {
            return
        }
        markMessageContentAsConsumedInteractively(messageId: message.id)
        """
        self.assertTrue(
            call_is_owned_by_exact_receipt_gate(
                exact_receipt,
                "markMessageContentAsConsumedInteractively",
            )
        )
        type_bound_exact_receipt = """
        if let item = item as? MessageMediaPlaylistItem {
            if consumeViewOnce || timeout != viewOnceTimeout {
                markMessageContentAsConsumedInteractively(messageId: item.message.id)
            }
        }
        """
        self.assertTrue(
            call_is_owned_by_exact_receipt_gate(
                type_bound_exact_receipt,
                "markMessageContentAsConsumedInteractively",
            )
        )
        optional_permission_mutant = """
        if let permission = optionalPermission {
            if consumeViewOnce || timeout != viewOnceTimeout {
                markMessageContentAsConsumedInteractively(messageId: message.id)
            }
        }
        """
        self.assertFalse(
            call_is_owned_by_exact_receipt_gate(
                optional_permission_mutant,
                "markMessageContentAsConsumedInteractively",
            )
        )
        alias_mutant = """
        let polarity = consumeViewOnce || true
        SharedMediaPlaybackDataSource.telegramFile(
            message: message,
            isViewOnce: polarity
        )
        func unrelated() {
            let polarity = consumeViewOnce && timeout == viewOnceTimeout
        }
        """
        alias_call = swift_calls(
            alias_mutant,
            "SharedMediaPlaybackDataSource.telegramFile",
        )[0]
        alias_argument = swift_top_level_argument(alias_call, "isViewOnce")
        self.assertFalse(
            is_exact_view_once_expression(
                resolve_swift_boolean_alias(
                    alias_mutant,
                    alias_argument,
                    before=alias_mutant.find(alias_call),
                )
            )
        )
        nested_receipt = """
        guard consumeViewOnce || timeout != viewOnceTimeout else {
            return
        }
        if unrelatedFlag {
            markMessageContentAsConsumedInteractively(messageId: message.id)
        }
        """
        self.assertFalse(
            call_is_owned_by_exact_receipt_gate(
                nested_receipt,
                "markMessageContentAsConsumedInteractively",
            )
        )

    def test_burn_rejects_true_only_prepare_gates(self) -> None:
        mutant = """
        TextAlertAction(type: .destructiveAction, action: {
            let signal = AyuGramHooks.prepareConsumableMedia?(accountPeerId, message)
            |> filter { $0 }
            |> mapToSignal { _ in
                context.engine.messages.markMessageContentAsConsumedInteractively(
                    messageId: message.id,
                    force: true
                )
            }
        })
        """
        self.assertFalse(burn_confirmation_ignores_prepare_bool(mutant))
        for true_only_gate in (
            """
            prepareConsumableMedia(accountPeerId, message)
            |> mapToSignal { prepared in
                guard prepared else { return .complete() }
                return markMessageContentAsConsumedInteractively(
                    messageId: message.id, force: true
                )
            }
            """,
            """
            prepareConsumableMedia(accountPeerId, message)
            |> mapToSignal { prepared in
                if prepared {
                    return markMessageContentAsConsumedInteractively(
                        messageId: message.id, force: true
                    )
                }
                return .complete()
            }
            """,
        ):
            self.assertFalse(burn_confirmation_ignores_prepare_bool(true_only_gate))
        valid = """
        prepareConsumableMedia(accountPeerId, message)
        |> mapToSignal { _ in
            markMessageContentAsConsumedInteractively(
                messageId: message.id,
                force: true
            )
        }
        """
        self.assertTrue(burn_confirmation_ignores_prepare_bool(valid))

    def test_replay_rejects_silent_fresh_row_failure(self) -> None:
        mutant = """
        restoreConsumableMedia(accountPeerId, message)
        |> mapToSignal { restored in
            guard restored else {
                present(textAlertController(text: strings.MediaUnavailable))
                return
            }
            guard let fresh = transaction.getMessage(message.id) else {
                return
            }
            controllerInteraction.openMessage(fresh, consumeOnOpen: false)
        }
        """
        self.assertEqual("", replay_fresh_row_fail_closed(mutant))
        valid = mutant.replace(
            "guard let fresh = transaction.getMessage(message.id) else {\n"
            "                return",
            "guard let fresh = transaction.getMessage(message.id) else {\n"
            "                present(textAlertController(text: strings.MediaUnavailable))\n"
            "                return",
        )
        self.assertEqual("fresh", replay_fresh_row_fail_closed(valid))
        valid_literal_alert = valid.replace(
            "strings.MediaUnavailable",
            '"Unavailable"',
        )
        self.assertEqual("fresh", replay_fresh_row_fail_closed(valid_literal_alert))
        opens_on_failure = valid.replace(
            "present(textAlertController(text: strings.MediaUnavailable))",
            "controllerInteraction.openMessage(message, consumeOnOpen: false)\n"
            "                present(textAlertController(text: strings.MediaUnavailable))",
        )
        self.assertEqual("", replay_fresh_row_fail_closed(opens_on_failure))
        nested_alert = mutant.replace(
            "guard let fresh = transaction.getMessage(message.id) else {\n"
            "                return",
            "guard let fresh = transaction.getMessage(message.id) else {\n"
            "                if unrelatedFlag {\n"
            "                    present(textAlertController(text: strings.MediaUnavailable))\n"
            "                }\n"
            "                return",
        )
        self.assertEqual("", replay_fresh_row_fail_closed(nested_alert))

    def test_sentinel_delete_requires_exact_key_and_attempt_resource_values(self) -> None:
        rollback_mutant = '''
        executePrepared(
            database,
            sql: """
            DELETE FROM archived_message_media
            WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
              AND message_id = ? AND thread_id = ? AND revision_id = ?
              AND resource_id = ?
            """,
            values: unrelated(
                self.keyValues(key),
                Self.consumableMediaRevisionId,
                resourceId
            )
        )
        '''
        rollback_call = swift_calls(rollback_mutant, "executePrepared")[0]
        self.assertFalse(
            exact_sentinel_delete_call(
                rollback_call,
                rollback_mutant,
                key_expression="key",
                sentinel_name="consumableMediaRevisionId",
                resource_expression="resourceId",
            )
        )

        transfer_mutant = '''
        executePrepared(
            database,
            sql: """
            DELETE FROM archived_message_media
            WHERE revision_id = ? AND resource_id = ?
            """,
            values: [.int64(Self.consumableMediaRevisionId), .text(record.resourceId)]
        )
        '''
        transfer_call = swift_calls(transfer_mutant, "executePrepared")[0]
        self.assertFalse(
            exact_sentinel_delete_call(
                transfer_call,
                transfer_mutant,
                key_expression="message.key",
                sentinel_name="consumableMediaRevisionId",
                resource_expression="record.resourceId",
            )
        )
        valid_rollback = rollback_mutant.replace(
            "unrelated(\n"
            "                self.keyValues(key),\n"
            "                Self.consumableMediaRevisionId,\n"
            "                resourceId\n"
            "            )",
            "self.keyValues(key) + [\n"
            "                .int64(Self.consumableMediaRevisionId),\n"
            "                .text(resourceId)\n"
            "            ]",
        )
        self.assertTrue(
            exact_sentinel_delete_call(
                swift_calls(valid_rollback, "executePrepared")[0],
                valid_rollback,
                key_expression="key",
                sentinel_name="consumableMediaRevisionId",
                resource_expression="resourceId",
            )
        )
        lowercase_or = valid_rollback.replace(
            "AND resource_id = ?",
            "AND resource_id = ? or 1 = 1",
        )
        self.assertFalse(
            exact_sentinel_delete_call(
                swift_calls(lowercase_or, "executePrepared")[0],
                lowercase_or,
                key_expression="key",
                sentinel_name="consumableMediaRevisionId",
                resource_expression="resourceId",
            )
        )

    def test_prepare_stable_id_mismatch_must_stop_before_probe(self) -> None:
        mutant = """
        func prepareConsumableMedia(_ message: Message) -> Bool {
            let fresh = transaction.getMessage(message.id)
            let stableMatches = fresh.stableId == message.stableId
            _ = stableMatches
            let path = completedResourcePath(resource)
            reserveConsumableMedia(key: key)
            return true
        }
        """
        self.assertEqual("", prepare_fresh_row_stable_id_fail_closed(mutant))
        valid = """
        guard let fresh = transaction.getMessage(message.id),
              fresh.stableId == message.stableId else {
            return false
        }
        let path = completedResourcePath(resource)
        """
        self.assertEqual("fresh", prepare_fresh_row_stable_id_fail_closed(valid))
        nested = """
        guard let fresh = transaction.getMessage(message.id) else {
            return false
        }
        if unrelatedFlag {
            if fresh.stableId != message.stableId {
                return false
            }
        }
        let path = completedResourcePath(resource)
        """
        self.assertEqual("", prepare_fresh_row_stable_id_fail_closed(nested))

    def test_prepare_idempotent_success_requires_positive_marker_gate(self) -> None:
        mutant = """
        let fresh = transaction.getMessage(message.id)
        if !fresh.attributes.contains(where: {
            $0 is GRVMPreservedConsumableMediaAttribute
        }) {
            return true
        }
        let path = completedResourcePath(resource)
        """
        self.assertFalse(prepare_positive_marker_idempotent_success(mutant, "fresh"))
        valid = mutant.replace("if !fresh.attributes", "if fresh.attributes")
        self.assertTrue(prepare_positive_marker_idempotent_success(valid, "fresh"))
        nested = """
        let fresh = transaction.getMessage(message.id)
        if legacyOverride {
            if fresh.attributes.contains(where: {
                $0 is GRVMPreservedConsumableMediaAttribute
            }) {
                return true
            }
        }
        let path = completedResourcePath(resource)
        """
        self.assertFalse(prepare_positive_marker_idempotent_success(nested, "fresh"))

    def test_prepare_terminal_checks_must_govern_marker_and_rollback(self) -> None:
        mutant = """
        let requiredPrimaryIds = requiredResources.map { $0.id }
        let terminalRecords = archivedRecords
        let terminalComplete = terminalRecords.allSatisfy {
            $0.complete && $0.byteCount > 0
        }
        let terminalIds = terminalRecords.map { $0.resourceId }.sorted()
        let exactSet = Set(requiredPrimaryIds) == Set(terminalIds)
        _ = terminalComplete
        _ = exactSet
        guard unrelatedFlag else {
            rollbackConsumableMediaReservation(insertedResourceIds: insertedResourceIds)
            return false
        }
        let marker = GRVMPreservedConsumableMediaAttribute(
            resourceIds: terminalIds,
            media: media,
            preparedAt: timestamp
        )
        """
        self.assertFalse(prepare_terminal_marker_fail_closed(mutant))
        valid = mutant.replace(
            "_ = terminalComplete\n        _ = exactSet\n        guard unrelatedFlag else {",
            "guard terminalComplete && exactSet else {",
        )
        self.assertTrue(prepare_terminal_marker_fail_closed(valid))
        conditional_rollback = valid.replace(
            "rollbackConsumableMediaReservation(insertedResourceIds: insertedResourceIds)",
            "if legacyOverride {\n"
            "                rollbackConsumableMediaReservation(insertedResourceIds: insertedResourceIds)\n"
            "            }",
        )
        self.assertFalse(prepare_terminal_marker_fail_closed(conditional_rollback))
        nested_gate = valid.replace(
            "guard terminalComplete && exactSet else {",
            "if unrelatedFlag {\n"
            "            guard terminalComplete && exactSet else {",
        ).replace(
            "        let marker = GRVMPreservedConsumableMediaAttribute(",
            "        }\n"
            "        let marker = GRVMPreservedConsumableMediaAttribute(",
        )
        self.assertFalse(prepare_terminal_marker_fail_closed(nested_gate))

    def test_local_copy_requires_cleanup_on_every_failure_path(self) -> None:
        mutant = """
        let temporaryPath = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
        do {
            try FileManager.default.linkItem(at: sourcePath, to: temporaryPath)
        } catch {
            try FileManager.default.copyItem(at: sourcePath, to: temporaryPath)
        }
        guard size > 0 else {
            return .fail(.unavailable)
        }
        let resource = LocalFileReferenceMediaResource(
            localFilePath: temporaryPath.path,
            size: size,
            isUniquelyReferencedTemporaryFile: true
        )
        return .message(
            text: message.text,
            mediaReference: .standalone(media: clone)
        )
        """
        self.assertFalse(
            local_copy_temp_cleanup_is_fail_closed(mutant, "temporaryPath")
        )
        guard_only = mutant.replace(
            "guard size > 0 else {\n            return .fail(.unavailable)",
            "guard size > 0 else {\n"
            "            try? FileManager.default.removeItem(at: temporaryPath)\n"
            "            return .fail(.unavailable)",
        )
        self.assertFalse(
            local_copy_temp_cleanup_is_fail_closed(guard_only, "temporaryPath")
        )
        catch_only = mutant.replace(
            "try FileManager.default.copyItem(at: sourcePath, to: temporaryPath)",
            "do {\n"
            "                try FileManager.default.copyItem(at: sourcePath, to: temporaryPath)\n"
            "            } catch {\n"
            "                try? FileManager.default.removeItem(at: temporaryPath)\n"
            "                return .fail(.unavailable)\n"
            "            }",
        )
        self.assertFalse(
            local_copy_temp_cleanup_is_fail_closed(catch_only, "temporaryPath")
        )
        valid = catch_only.replace(
            "guard size > 0 else {\n            return .fail(.unavailable)",
            "guard size > 0 else {\n"
            "            try? FileManager.default.removeItem(at: temporaryPath)\n"
            "            return .fail(.unavailable)",
        )
        self.assertTrue(
            local_copy_temp_cleanup_is_fail_closed(valid, "temporaryPath")
        )
        deletes_before_handoff = valid.replace(
            "let resource = LocalFileReferenceMediaResource(",
            "try? FileManager.default.removeItem(at: temporaryPath)\n"
            "        let resource = LocalFileReferenceMediaResource(",
        )
        self.assertFalse(
            local_copy_temp_cleanup_is_fail_closed(
                deletes_before_handoff,
                "temporaryPath",
            )
        )

    def test_local_copy_message_attributes_are_allowlist_only(self) -> None:
        mutant = """
        var safeAttributes: [MessageAttribute] = []
        safeAttributes.append(TextEntitiesMessageAttribute(entities: entities))
        let inherited = message.attributes
        safeAttributes.append(contentsOf: inherited)
        return .message(
            text: message.text,
            attributes: safeAttributes,
            mediaReference: .standalone(media: clone)
        )
        """
        message_call = [
            call
            for call in swift_calls(mutant, ".message")
            if "mediaReference:" in call
        ][0]
        self.assertFalse(message_attributes_are_allowlist_only(mutant, message_call))
        tainted_variants = (
            mutant.replace(
                "let inherited = message.attributes\n"
                "        safeAttributes.append(contentsOf: inherited)",
                "safeAttributes += message.attributes",
            ),
            mutant.replace(
                "safeAttributes.append(contentsOf: inherited)",
                "safeAttributes = inherited",
            ),
            mutant.replace(
                "attributes: safeAttributes",
                "attributes: forwardedAttributes",
            ).replace(
                "let inherited = message.attributes",
                "let inherited = message.attributes\n"
                "        let forwardedAttributes = safeAttributes",
            ),
        )
        for tainted in tainted_variants:
            tainted_call = [
                call
                for call in swift_calls(tainted, ".message")
                if "mediaReference:" in call
            ][0]
            self.assertFalse(message_attributes_are_allowlist_only(tainted, tainted_call))
        valid = mutant.replace(
            "let inherited = message.attributes\n"
            "        safeAttributes.append(contentsOf: inherited)\n",
            "",
        )
        valid_call = [
            call
            for call in swift_calls(valid, ".message")
            if "mediaReference:" in call
        ][0]
        self.assertTrue(message_attributes_are_allowlist_only(valid, valid_call))
        hidden_alias = """
        let inherited = message.attributes
        var safeAttributes: [MessageAttribute] = []
        safeAttributes.append(TextEntitiesMessageAttribute(entities: entities))
        safeAttributes.insert(inherited[0], at: 0)
        return .message(
            text: message.text,
            attributes: safeAttributes,
            mediaReference: .standalone(media: clone)
        )
        """
        hidden_alias_call = [
            call
            for call in swift_calls(hidden_alias, ".message")
            if "mediaReference:" in call
        ][0]
        self.assertFalse(
            message_attributes_are_allowlist_only(hidden_alias, hidden_alias_call)
        )


class ConsumeLifecycleContractTests(SourceContractTestCase):
    def test_preserved_consumable_attribute_codec_equality_and_registration(self) -> None:
        attribute = source(
            "submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift"
        )
        self.assertContainsAll(
            attribute,
            "public final class GRVMPreservedConsumableMediaAttribute: MessageAttribute, Equatable",
            "public let resourceIds: [String]",
            "public let media: [Media]",
            "public let preparedAt: Int32",
            "public init(resourceIds: [String], media: [Media], preparedAt: Int32)",
            "public required init(decoder: PostboxDecoder)",
            'decodeStringArrayForKey("r")',
            'decodeObjectArrayForKey("m").compactMap { $0 as? Media }',
            'decodeInt32ForKey("t", orElse: 0)',
            'encodeStringArray(self.resourceIds, forKey: "r")',
            'encodeInt32(self.preparedAt, forKey: "t")',
            "areMediaArraysEqual(lhs.media, rhs.media)",
            "self.media = media",
        )
        encoding = swift_block(attribute, "public func encode(")
        self.assertContains(
            encoding,
            'encoder.encodeGenericObjectArray(self.media.map { $0 as PostboxCoding }, forKey: "m")',
        )
        self.assertNotContains(
            encoding,
            'encoder.encodeObjectArray(self.media, forKey: "m")',
        )
        equality = swift_block(attribute, "public static func ==(")
        self.assertContainsAll(equality, "resourceIds", "preparedAt", "areMediaArraysEqual")
        self.assertMatches(attribute, r"self\.resourceIds\s*=.*\.sorted\(")
        for forbidden in ("relativePath", "absolutePath", "archivePath", "payload", "accountId"):
            self.assertNotContains(attribute, forbidden)

        account_manager = source("submodules/TelegramCore/Sources/Account/AccountManager.swift")
        self.assertContains(
            account_manager,
            "declareEncodable(GRVMPreservedConsumableMediaAttribute.self, f: { GRVMPreservedConsumableMediaAttribute(decoder: $0) })",
        )

    def test_force_operation_defaults_round_trips_and_builder_propagates(self) -> None:
        operation = source(
            "submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift"
        )
        builder = source(
            "submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift"
        )
        self.assertContainsAll(
            operation,
            "public let force: Bool",
            'self.force = decoder.decodeInt32ForKey("f", orElse: 0) != 0',
            'encoder.encodeInt32(self.force ? 1 : 0, forKey: "f")',
        )
        self.assertMatches(
            operation,
            r"public init\(messageIds: \[MessageId\],\s*force: Bool = false\)",
        )
        self.assertMatches(builder, r"(?s)func addSynchronizeConsumeMessageContentsOperation.*force: Bool = false")
        self.assertContains(builder, "SynchronizeConsumeMessageContentsOperation(messageIds: messageIds, force: force)")

    def test_public_and_internal_force_api_bypass_only_ghost_suppression(self) -> None:
        interactive = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
        )
        engine = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift"
        )
        worker = source(
            "submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift"
        )
        internal_method = swift_block(
            interactive,
            "func _internal_markMessageContentAsConsumedInteractively(",
        )
        public_method = swift_block(
            engine,
            "public func markMessageContentAsConsumedInteractively(",
        )
        self.assertContains(internal_method, "force: Bool = false")
        self.assertContains(internal_method, "shouldSuppressContentRead?(accountPeerId) == true && !force")
        self.assertContains(internal_method, "force: force")
        self.assertContains(public_method, "force: Bool = false")
        self.assertContains(public_method, "force: force")
        self.assertContains(worker, "shouldSuppressContentRead?(stateManager.accountPeerId) == true && !operation.force")

    def test_consume_worker_keeps_stock_user_channel_and_pts_routes(self) -> None:
        worker = source(
            "submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift"
        )
        builder = source(
            "submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift"
        )
        self.assertContainsAll(
            worker,
            "Api.functions.messages.readMessageContents",
            "Api.functions.channels.readMessageContents",
            "apiInputChannel(peer)",
            ".updatePts(pts: pts, ptsCount: ptsCount)",
            "operation.messageIds",
        )
        self.assertContains(builder, "operationLogRemoveEntry")

    def test_remote_consume_callers_pass_exact_account_identity(self) -> None:
        remote = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
        )
        account_state = source(
            "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift"
        )
        secret_state = source(
            "submodules/TelegramCore/Sources/State/ProcessSecretChatIncomingDecryptedOperations.swift"
        )
        remote_method = swift_block(remote, "func markMessageContentAsConsumedRemotely(")
        self.assertContains(remote_method, "accountPeerId: PeerId")
        pattern = re.compile(
            r"markMessageContentAsConsumedRemotely\(\s*"
            r"accountPeerId:\s*accountPeerId,\s*"
            r"transaction:\s*transaction,",
            re.DOTALL,
        )
        self.assertEqual(2, len(pattern.findall(account_state)))
        self.assertEqual(1, len(pattern.findall(secret_state)))

    def test_remote_consume_updates_lifecycle_but_marker_alone_retains_media(self) -> None:
        remote = swift_without_comments(swift_block(
            source(
                "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
            ),
            "func markMessageContentAsConsumedRemotely(",
        ))
        self.assertContainsAll(
            remote,
            "GRVMPreservedConsumableMediaAttribute",
            "ConsumableContentMessageAttribute(consumed: true)",
            "ConsumablePersonalMentionMessageAttribute(consumed: true, pending: false)",
            "updatedTags.remove(.unseenPersonalMessage)",
            "AutoremoveTimeoutMessageAttribute",
            "AutoclearTimeoutMessageAttribute",
            "TelegramMediaExpiredContent",
        )
        self.assertNotContains(remote, "shouldPreserveOneTimeMedia")
        self.assertNotContains(remote, "shouldSuppressContentRead")
        marker_gate = re.search(
            r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"message\.attributes\.contains\(where:\s*\{\s*\$0 is "
            r"GRVMPreservedConsumableMediaAttribute\s*\}\)",
            remote,
        )
        if marker_gate is not None:
            gate_name = marker_gate.group(1)
            marker_negative_ranges = swift_condition_ranges(remote, gate_name)
            self.assertTrue(
                all_occurrences_in_ranges(
                    remote, "TelegramMediaExpiredContent", marker_negative_ranges
                ),
                msg="Every expired-media replacement must be owned by the durable-marker-negative branch",
            )
            first_expiration_gate = min(start for start, _ in marker_negative_ranges)
            for lifecycle_anchor in (
                "ConsumableContentMessageAttribute(consumed: true)",
                "ConsumablePersonalMentionMessageAttribute(consumed: true, pending: false)",
                "updatedTags.remove(.unseenPersonalMessage)",
            ):
                self.assertLess(remote.find(lifecycle_anchor), first_expiration_gate)
        else:
            self.fail("Remote consume must expose an explicit durable-marker gate")

    def test_autoremove_marker_gate_does_not_bypass_whole_message_deletion(self) -> None:
        autoremove = swift_without_comments(
            source(
                "submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift"
            )
        )
        self.assertContainsAll(
            autoremove,
            "message.id.peerId.namespace == Namespaces.Peer.SecretChat || isRemove",
            "_internal_applyMessageDeletion(",
            "mode: .server(.ttl)",
            "GRVMPreservedConsumableMediaAttribute",
            "AutoclearTimeoutMessageAttribute",
            "TelegramMediaExpiredContent",
        )
        self.assertOrdered(
            autoremove,
            "message.id.peerId.namespace == Namespaces.Peer.SecretChat || isRemove",
            "GRVMPreservedConsumableMediaAttribute",
        )
        self.assertNotContains(autoremove, "shouldPreserveOneTimeMedia")
        marker_gate = re.search(
            r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"message\.attributes\.contains\(where:\s*\{\s*\$0 is "
            r"GRVMPreservedConsumableMediaAttribute\s*\}\)",
            autoremove,
        )
        if marker_gate is not None:
            marker_name = marker_gate.group(1)
            timer_removal_patterns = (
                r"(?s)removeAll\s*\{.*?AutoclearTimeoutMessageAttribute",
                r"(?s)=\s*\w+\.filter\s*\{.*?AutoclearTimeoutMessageAttribute",
                r"(?s)if\s+let\s+_\s*=\s*(?P<array>\w+)\[(?P<index>\w+)\]\s+as\?\s+"
                r"AutoclearTimeoutMessageAttribute.*?(?P=array)\.remove\(at:\s*(?P=index)\)",
            )
            marker_branches = swift_exact_positive_if_blocks(autoremove, marker_name)
            retained_branches = [
                branch
                for branch in marker_branches
                if any(re.search(pattern, branch) for pattern in timer_removal_patterns)
            ]
            self.assertEqual(
                1,
                len(retained_branches),
                msg="The retained row must structurally remove its autoclear timer",
            )
            marker_branch = retained_branches[0]
            self.assertAnyContains(marker_branch, "media: currentMessage.media", ".withUpdatedMedia(")
            self.assertNotContains(marker_branch, "TelegramMediaExpiredContent")
            self.assertTrue(
                all_occurrences_in_ranges(
                    autoremove,
                    "TelegramMediaExpiredContent",
                    swift_condition_ranges(autoremove, marker_name),
                ),
                msg="Autoremove may expire media only when the durable marker is absent",
            )
        else:
            self.fail("Autoremove must expose an explicit durable-marker branch")

    def test_bulk_and_edit_merges_retain_marker_but_restore_only_expired_media(self) -> None:
        standalone = source(
            "submodules/TelegramCore/Sources/SyncCore/SyncCore_StandaloneAccountTransaction.swift"
        )
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        account_state = source(
            "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift"
        )
        bulk = around(account_state, "transaction.addMessages(messages, location: location)", 6500, 200)
        edit = around(account_state, "case let .EditMessage(id, message):", 0, 6500)
        attribute_merge = swift_block(hooks, "func grvmMergedEditStateAttributes(")
        media_merge = swift_block(hooks, "func grvmMergedEditedMessage(")
        for merge_path in (standalone, attribute_merge, media_merge, bulk, edit):
            self.assertNotContains(swift_without_comments(merge_path), "shouldPreserveOneTimeMedia")
        self.assertContains(standalone, "mergeMessageAttributes")
        self.assertMatches(
            standalone,
            r"(?s)if let\s+(?P<standaloneMarker>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"previous\.first\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"!updated\.contains\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"updated\.append\(\s*(?P=standaloneMarker)\s*\)",
        )
        self.assertMatches(
            attribute_merge,
            r"(?s)if let\s+(?P<attributeMarker>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"previous\.first\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"result\.removeAll\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"result\.append\(\s*(?P=attributeMarker)\s*\)",
        )
        marker_binding = re.search(
            r"if let\s+(?P<marker>[A-Za-z_][A-Za-z0-9_]*)\s*=.*"
            r"GRVMPreservedConsumableMediaAttribute",
            media_merge,
            re.DOTALL,
        )
        self.assertIsNotNone(marker_binding, msg="Media merge must bind the durable marker")
        marker_name = marker_binding.group("marker")
        expired_gate = re.search(
            r"(?:if|guard)\s+[^\n{]*incoming\.media[^\n{]*"
            r"TelegramMediaExpiredContent[^\n{]*\{",
            media_merge,
        )
        self.assertIsNotNone(expired_gate, msg="Marker media may replace only expired incoming media")
        expired_branch, _ = swift_block_at(media_merge, expired_gate.start())
        self.assertMatches(
            expired_branch,
            rf"updatedMedia\s*=\s*{re.escape(marker_name)}\.media",
        )
        marker_media_sites = occurrence_positions(media_merge, f"{marker_name}.media")
        expired_start = expired_gate.start()
        expired_end = expired_start + len(expired_branch)
        self.assertTrue(
            marker_media_sites
            and all(expired_start <= site < expired_end for site in marker_media_sites),
            msg="No non-expired merge path may substitute marker media",
        )
        self.assertMatches(
            media_merge,
            r"(?s)(?:var|let)\s+updatedMedia[^=]*=\s*incoming\.media|"
            r"else\s*\{[^}]*updatedMedia\s*=\s*incoming\.media|"
            r"return\s+incoming",
        )
        self.assertContainsAll(
            bulk,
            "transaction.getMessage(",
            "grvmMergedEditedMessage(",
            "transaction.addMessages(messages, location: location)",
        )
        bulk_assignment = re.search(
            r"(?s)(?:messages\[[^\]]+\]\s*=\s*grvmMergedEditedMessage\(|"
            r"messages\s*=\s*messages\.(?:map|compactMap)\s*\{.*?"
            r"grvmMergedEditedMessage\()",
            bulk,
        )
        self.assertIsNotNone(
            bulk_assignment,
            msg="Bulk merge must store the marker-preserving message before addMessages",
        )
        self.assertOrdered(bulk, "grvmMergedEditedMessage(", "transaction.addMessages(messages, location: location)")
        self.assertContains(edit, "grvmMergedEditStateAttributes(")
        if "grvmMergedEditedMessage(" not in edit:
            self.assertMatches(
                edit,
                r"(?s)if let\s+(?P<marker>[A-Za-z_][A-Za-z0-9_]*)\s*=.*"
                r"GRVMPreservedConsumableMediaAttribute.*TelegramMediaExpiredContent.*"
                r"updatedMedia\s*=\s*(?P=marker)\.media",
            )
        self.assertOrdered(edit, "grvmMergedEditStateAttributes(", ".update")

    def test_force_and_marker_behavior_fixtures_cover_fail_closed_edges(self) -> None:
        false_positive = """
        let hasMarker = true
        if !hasMarker { updateCountdown() }
        if !hasMarker { updateMention() }
        media = [TelegramMediaExpiredContent(data: nil)]
        """
        self.assertFalse(
            all_occurrences_in_ranges(
                false_positive,
                "TelegramMediaExpiredContent",
                swift_condition_ranges(false_positive, "hasMarker"),
            )
        )
        self.assertEqual([False, False, True], [decode_force(payload) for payload in ({}, {"f": 0}, {"f": 1})])
        self.assertEqual(
            [True, True, False, True],
            [
                sends_content_read(suppressed=suppressed, force=force)
                for suppressed, force in ((False, False), (False, True), (True, False), (True, True))
            ],
        )
        self.assertEqual(
            [
                (False, "expired"),
                (True, "preserved"),
                (False, "updated"),
                (True, "updated"),
            ],
            [
                merged_media(marker=marker, incoming=incoming)
                for marker, incoming in (
                    (False, "expired"),
                    (True, "expired"),
                    (False, "updated"),
                    (True, "updated"),
                )
            ],
        )
        cases = (
            (False, False, False, False, False, "expire-clear-timer"),
            (False, False, False, True, True, "expire-clear-timer"),
            (False, False, True, False, False, "retain-clear-timer"),
            (True, False, True, False, False, "delete"),
            (False, True, True, True, True, "delete"),
        )
        for secret, is_remove, marker, legacy, ghost, expected in cases:
            self.assertEqual(
                expected,
                autoremove_outcome(
                    secret=secret,
                    is_remove=is_remove,
                    marker=marker,
                    legacy=legacy,
                    ghost=ghost,
                ),
            )


class ArchiveHooksSentinelContractTests(SourceContractTestCase):
    def test_primary_resource_fixture_requires_positive_sorted_unique_ids(self) -> None:
        self.assertEqual(
            ("file-a", "photo-z"),
            primary_resource_ids([("photo-z", 20), ("file-a", 30), ("photo-z", 20)]),
        )
        self.assertIsNone(primary_resource_ids([]))
        self.assertIsNone(primary_resource_ids([("photo-z", 20), ("file-a", 0)]))
        good_records = (
            ArchivedMediaRecord("account-a", "message-1", "photo-z", byte_count=20),
            ArchivedMediaRecord("account-a", "message-1", "file-a", byte_count=30),
        )
        complete, rollback = prepare_terminal_outcome(
            good_records,
            required_ids=("file-a", "photo-z"),
        )
        self.assertTrue(complete)
        self.assertEqual((), rollback)
        complete, rollback = prepare_terminal_outcome(
            (ArchivedMediaRecord("account-a", "message-1", "file-a", byte_count=0),)
        )
        self.assertFalse(complete)
        self.assertEqual(("file-a",), rollback)

        invalid_terminal_sets = (
            good_records[:1],
            good_records + (ArchivedMediaRecord("account-a", "message-1", "extra"),),
            good_records + (good_records[0],),
            (replace(good_records[0], account="account-b"), good_records[1]),
            (replace(good_records[0], message_key="message-2"), good_records[1]),
            (replace(good_records[0], complete=False), good_records[1]),
            (replace(good_records[0], byte_count=0), good_records[1]),
        )
        self.assertTrue(
            terminal_set_authorized(
                required_ids=("file-a", "photo-z"),
                account="account-a",
                message_key="message-1",
                records=good_records,
            )
        )
        for records in invalid_terminal_sets:
            self.assertFalse(
                terminal_set_authorized(
                    required_ids=("file-a", "photo-z"),
                    account="account-a",
                    message_key="message-1",
                    records=records,
                )
            )

        events = ["probe:file-a", "probe:photo-z", "reserve"]
        events += ["archive:file-a", "persist:file-a", "archive:photo-z", "persist:photo-z"]
        events += ["verify-all-complete", "attach-marker"]
        last_persist = max(index for index, event in enumerate(events) if event.startswith("persist:"))
        self.assertLess(last_persist, events.index("attach-marker"))
        self.assertEqual(
            ("reread", "return-success"),
            prepare_event_trace(existing_marker=True, terminal_valid=False),
        )
        self.assertEqual(
            ("reread", "probe", "reserve", "archive", "persist-terminal", "rollback", "return-false"),
            prepare_event_trace(existing_marker=False, terminal_valid=False),
        )

    def test_sentinel_fixture_is_idempotent_transfers_and_counts_all_revisions(self) -> None:
        database = sqlite_sentinel_fixture()
        key = (7, 100, 0, 42, 0)
        database.execute(
            """
            INSERT INTO archived_media_blobs
                (account_id, resource_id, relative_path, byte_count, kind, copy_state, generation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (7, "primary", "7/blobs/aa/primary", 64, "file", 2, 9),
        )
        reserve = """
            INSERT OR IGNORE INTO archived_message_media
                (account_id, peer_id, message_namespace, message_id,
                 thread_id, revision_id, resource_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        database.execute(reserve, (*key, -1, "primary"))
        database.execute(reserve, (*key, -1, "primary"))
        self.assertEqual(
            1,
            database.execute(
                "SELECT COUNT(*) FROM archived_message_media WHERE revision_id = -1"
            ).fetchone()[0],
        )
        self.assertEqual(
            (2, 9),
            database.execute(
                "SELECT copy_state, generation FROM archived_media_blobs"
            ).fetchone(),
        )

        database.execute(reserve, (*key, 0, "primary"))
        database.execute(
            """
            DELETE FROM archived_message_media
            WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
              AND message_id = ? AND thread_id = ? AND revision_id = -1
              AND resource_id = ?
            """,
            (*key, "primary"),
        )
        self.assertEqual(
            [(0,)],
            database.execute(
                "SELECT revision_id FROM archived_message_media ORDER BY revision_id"
            ).fetchall(),
        )
        self.assertEqual(
            1,
            database.execute(
                "SELECT COUNT(*) FROM archived_message_media WHERE resource_id = ?",
                ("primary",),
            ).fetchone()[0],
        )
        database.close()

    def test_failed_attempt_fixture_removes_only_attempt_owned_sentinels(self) -> None:
        mappings = {
            ("old", -1, "kept"),
            ("attempt", -1, "shared"),
            ("deleted", 0, "shared"),
            ("attempt", -1, "orphan"),
        }
        planned_for_attempt = ("kept", "shared", "orphan")
        inserted_by_attempt = ("shared", "orphan")
        self.assertEqual(
            {"kept"},
            set(planned_for_attempt) - set(inserted_by_attempt),
            msg="A reused sentinel is planned but never owned by this attempt",
        )
        for terminal_outcome in (
            "archiveIncomplete",
            "terminalDatabaseFailure",
            "stalePostboxRow",
            "markerWriteFailure",
        ):
            with self.subTest(terminal_outcome=terminal_outcome):
                rollback_ids = rollback_attempt_resources(
                    inserted_resource_ids=inserted_by_attempt,
                    terminal_outcome=terminal_outcome,
                )
                remaining = {
                    row
                    for row in mappings
                    if not (
                        row[0] == "attempt"
                        and row[1] == -1
                        and row[2] in rollback_ids
                    )
                }
                referenced = {row[2] for row in remaining}
                removable = set(inserted_by_attempt) - referenced
                self.assertEqual(("orphan", "shared"), rollback_ids)
                self.assertIn(("old", -1, "kept"), remaining)
                self.assertNotIn("kept", rollback_ids)
                self.assertIn("shared", referenced)
                self.assertNotIn("orphan", referenced)
                self.assertEqual({"orphan"}, removable)
        self.assertEqual(
            (),
            rollback_attempt_resources(
                inserted_resource_ids=inserted_by_attempt,
                terminal_outcome="markerAttached",
            ),
        )

    def test_exact_account_hook_fixture_never_falls_back_to_primary(self) -> None:
        calls: list[tuple[str, str]] = []
        services = {"account-a": "owner-a", "account-b": "owner-b"}

        def hook(account_id: str, message_id: str) -> bool:
            owner = services.get(account_id)
            if owner is None:
                return False
            calls.append((owner, message_id))
            return True

        self.assertTrue(hook("account-b", "same-message-id"))
        self.assertFalse(hook("missing", "same-message-id"))
        self.assertEqual([("owner-b", "same-message-id")], calls)

    def test_archive_hooks_are_symmetric_exact_account_and_fail_closed(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        manager = source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift")
        self.assertContains(hooks, "import SwiftSignalKit")
        self.assertContainsAll(
            hooks,
            "public static var prepareConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?",
            "public static var restoreConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?",
        )
        for hook_name, service_call in (
            ("prepareConsumableMedia", "service.prepareConsumableMedia(message)"),
            ("restoreConsumableMedia", "service.restoreArchivedMedia(for: message)"),
        ):
            signature = f"AyuGramHooks.{hook_name} = {{ [weak self] accountPeerId, message in"
            block = swift_block(
                manager,
                signature,
            )
            self.assertContainsAll(
                block,
                signature,
                "guard let service = self?.registry.service(accountPeerId: accountPeerId) else",
                "registry.service(accountPeerId: accountPeerId)",
                ".single(false)",
                service_call,
            )
            self.assertNotContains(block, "primaryService")
            self.assertNotContains(block, "currentSettings")

    def test_prepare_reloads_exact_row_and_selects_positive_primary_resources(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
        )
        prepare = swift_block(coordinator, "public func prepareConsumableMedia(")
        self.assertContainsAll(
            prepare,
            "public func prepareConsumableMedia(_ message: Message) -> Signal<Bool, NoError>",
            "settingsSnapshot().saveDeletedMessages",
            "postbox.transaction",
            "transaction.getMessage(message.id)",
            "self.messageKey(",
            "accountRecordId",
            "stableId",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "largestImageRepresentation(image.representations)",
            "file.resource",
            "grvmMediaResources(",
            "Set(",
            ".filter",
            "id.stringRepresentation",
            ".sorted()",
            "completedResourcePath",
        )
        self.assertMatches(prepare, r"(?s)(fileSize|byteCount|size).*?>\s*0")
        self.assertMatches(
            prepare,
            r"(?s)(?:allSatisfy|\.all\s*\{).*?\.complete.*?(?:byteCount|size)\s*>\s*0",
        )
        self.assertMatches(
            prepare,
            r"(?s)grvmMediaResources\(.*?\).*?\.filter.*?"
            r"(?:[Pp]rimary|[Rr]equired)[A-Za-z]*Ids.*?contains",
        )
        self.assertNotContains(prepare, "message.id.peerId == self.accountPeerId")
        row_binding = re.search(
            r"(?:guard\s+let|if\s+let|let)\s+(?P<row>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"transaction\.getMessage\(message\.id\)",
            prepare,
        )
        self.assertIsNotNone(row_binding, msg="Preparation must bind the freshly re-read Postbox row")
        row_name = row_binding.group("row")
        self.assertEqual(
            row_name,
            prepare_fresh_row_stable_id_fail_closed(prepare),
            msg="A fresh-row stableId mismatch must return false before any probe or reservation",
        )
        self.assertContains(prepare, f"{row_name}.media")
        self.assertRegex(
            prepare,
            rf"grvmMediaResources\(\s*{re.escape(row_name)}\s*\)",
        )
        probe_position = prepare.find("completedResourcePath")
        idempotent_prefix = prepare[row_binding.end() : probe_position]
        self.assertTrue(
            prepare_positive_marker_idempotent_success(prepare, row_name),
            msg="A valid existing marker must return success before probing or reserving bytes",
        )
        self.assertNotContains(idempotent_prefix, "GRVMPreservedConsumableMediaAttribute(")
        self.assertNotContains(idempotent_prefix, "reserveConsumableMedia(")
        self.assertNotContains(idempotent_prefix, "mediaStore.archive(")
        self.assertNotContains(idempotent_prefix, "transaction.updateMessage")
        self.assertRegex(
            prepare,
            r"(?s)(?:self\.)?messageKey\([^)]*\).*?accountRecordId|"
            r"accountRecordId.*?(?:self\.)?messageKey\(",
        )
        for forbidden in ("network.request", "fetchedResource", "resourceData(", "fetchResource"):
            self.assertNotContains(prepare, forbidden)

    def test_prepare_persists_every_terminal_record_before_attaching_marker(self) -> None:
        prepare = swift_block(
            source("submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"),
            "public func prepareConsumableMedia(",
        )
        self.assertContainsAll(
            prepare,
            "reserveConsumableMedia(",
            "mediaStore.archive(",
            "store.updateMedia(",
            "rollbackConsumableMediaReservation(",
            "insertedResourceIds",
            ".complete",
            "byteCount > 0",
            "GRVMPreservedConsumableMediaAttribute(",
        )
        self.assertGreaterEqual(prepare.count("GRVMPreservedConsumableMediaAttribute"), 2)
        self.assertGreaterEqual(prepare.count("transaction.getMessage(message.id)"), 2)
        self.assertLess(
            prepare.find("settingsSnapshot().saveDeletedMessages"),
            prepare.rfind("GRVMPreservedConsumableMediaAttribute("),
        )
        self.assertLess(prepare.find("completedResourcePath"), prepare.find("reserveConsumableMedia("))
        self.assertLess(prepare.find("reserveConsumableMedia("), prepare.find("mediaStore.archive("))
        self.assertLess(prepare.find("mediaStore.archive("), prepare.find("store.updateMedia("))
        marker_position = prepare.rfind("GRVMPreservedConsumableMediaAttribute(")
        required_binding = re.search(
            r"(?:let|var)\s+(?P<required>[A-Za-z_][A-Za-z0-9_]*(?:primary|required)"
            r"[A-Za-z0-9_]*Ids)\s*=",
            prepare,
            re.IGNORECASE,
        )
        self.assertIsNotNone(required_binding, msg="Preparation must retain the required primary-ID set")
        required_ids = required_binding.group("required")
        terminal_validation = re.search(
            r"(?s)\b([A-Za-z_][A-Za-z0-9_]*)\.(?:allSatisfy|all)\s*"
            r"(?:\(\s*)?\{.*?\.complete.*?(?:byteCount|size)\s*>\s*0",
            prepare,
        )
        self.assertIsNotNone(
            terminal_validation,
            msg="Marker eligibility must be derived from verified terminal archive records",
        )
        validated_records = terminal_validation.group(1)
        marker_calls = swift_calls(prepare, "GRVMPreservedConsumableMediaAttribute")
        self.assertGreaterEqual(len(marker_calls), 1)
        marker_ids = re.search(
            r"(?s)\bresourceIds\s*:\s*(.*?)\s*,\s*media\s*:",
            marker_calls[-1],
        )
        self.assertIsNotNone(marker_ids, msg="Marker must declare its verified resource IDs")
        derived_ids = re.findall(
            rf"(?s)(?:let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            rf"{re.escape(validated_records)}\.(?:map|compactMap).*?"
            r"resourceId.*?\.sorted\(\)",
            prepare[:marker_position],
        )
        self.assertTrue(
            derived_ids,
            msg="Verified terminal records must produce sorted marker resource IDs",
        )
        terminal_id_expressions = tuple(derived_ids)
        set_equal_patterns = []
        for terminal_ids in terminal_id_expressions:
            set_equal_patterns.extend(
                (
                    rf"Set\(\s*{re.escape(required_ids)}\s*\)\s*==\s*"
                    rf"Set\(\s*{re.escape(terminal_ids)}(?:\.[^)]*)?\s*\)",
                    rf"Set\(\s*{re.escape(terminal_ids)}(?:\.[^)]*)?\s*\)\s*==\s*"
                    rf"Set\(\s*{re.escape(required_ids)}\s*\)",
                    rf"\b{re.escape(required_ids)}\b\s*==\s*\b{re.escape(terminal_ids)}\b",
                    rf"\b{re.escape(terminal_ids)}\b\s*==\s*\b{re.escape(required_ids)}\b",
                )
            )
        self.assertTrue(
            any(re.search(pattern, prepare[:marker_position], re.DOTALL) for pattern in set_equal_patterns),
            msg="Terminal record IDs must be set-equal to every required primary ID before marker write",
        )
        self.assertTrue(
            any(
                re.search(rf"\b{re.escape(derived_id)}\b", marker_ids.group(1))
                for derived_id in derived_ids
            ),
            msg="Marker resourceIds must come from the complete terminal record set",
        )
        archive_positions = [
            match.start() for match in re.finditer(r"mediaStore\.archive\(", prepare)
        ]
        update_positions = [
            match.start() for match in re.finditer(r"store\.updateMedia\(", prepare)
        ]
        self.assertTrue(archive_positions)
        self.assertTrue(update_positions)
        self.assertGreaterEqual(len(update_positions), len(archive_positions))
        self.assertLess(max(archive_positions), marker_position)
        self.assertLess(max(update_positions), marker_position)
        self.assertEqual(
            len(update_positions),
            len(re.findall(r"store\.updateMedia\(", prepare[:marker_position])),
        )
        self.assertLess(max(update_positions), prepare.rfind("transaction.getMessage(message.id)"))
        self.assertLess(
            prepare.rfind("transaction.getMessage(message.id)"),
            prepare.rfind("GRVMPreservedConsumableMediaAttribute("),
        )
        persist_iteration_patterns = (
            rf"(?s)for\s+(?P<record>[A-Za-z_]\w*)\s+in\s+{re.escape(validated_records)}\s*\{{"
            rf".*?store\.updateMedia\([^)]*(?P=record)",
            rf"(?s){re.escape(validated_records)}\.(?:forEach|map|compactMap)\s*\{{\s*"
            rf"(?P<record>[A-Za-z_]\w*)\s+in.*?store\.updateMedia\([^)]*(?P=record)",
            r"(?s)mediaStore\.archive\(.*?\|>\s*(?:map|mapToSignal)\s*\{\s*"
            r"(?P<record>[A-Za-z_]\w*)\s+in.*?store\.updateMedia\([^)]*(?P=record)",
        )
        self.assertTrue(
            any(re.search(pattern, prepare) for pattern in persist_iteration_patterns),
            msg="Each archive terminal record must flow through store.updateMedia",
        )
        reservation_binding = re.search(
            r"(?:let|var|guard\s+let)\s+([A-Za-z_][A-Za-z0-9_]*)"
            r"(?:\s*:\s*[^=\n]+)?\s*=\s*(?:try[?!]?\s+)?"
            r"(?:self\.)?store\.reserveConsumableMedia\(",
            prepare,
        )
        tuple_binding = re.search(
            r"(?:let|var|guard\s+let)\s*\(([^)]+)\)\s*=\s*"
            r"(?:try[?!]?\s+)?(?:self\.)?store\.reserveConsumableMedia\(",
            prepare,
        )
        if reservation_binding is not None:
            reservation_expressions = (
                f"{reservation_binding.group(1)}.insertedResourceIds",
            )
        elif tuple_binding is not None:
            tuple_names = [name.strip() for name in tuple_binding.group(1).split(",")]
            reservation_expressions = tuple(
                name for name in tuple_names if "inserted" in name.lower()
            )
            self.assertTrue(
                reservation_expressions,
                msg="Tuple reservation result must expose its attempt-owned inserted IDs",
            )
        else:
            reservation_expressions = ()
            self.fail("The reservation result must expose attempt-owned insertedResourceIds")
        rollback_calls = swift_calls(prepare, "rollbackConsumableMediaReservation")
        self.assertGreaterEqual(len(rollback_calls), 1)
        for rollback_call in rollback_calls:
            argument = re.search(
                r"\binsertedResourceIds\s*:\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
                rollback_call,
            )
            self.assertIsNotNone(argument, msg="Rollback must name its attempt-owned ID set")
            argument_expression = argument.group(1)
            direct_match = any(
                argument_expression == expression for expression in reservation_expressions
            )
            alias_match = any(
                re.search(
                    rf"(?:let|var)\s+{re.escape(argument_expression)}\s*=\s*"
                    rf"{re.escape(expression)}\b",
                    prepare,
                )
                for expression in reservation_expressions
            )
            self.assertTrue(
                direct_match or alias_match,
                msg="Rollback IDs must flow from the reservation's insertedResourceIds",
            )
            self.assertNotContains(rollback_call, "resourceIds: []")
        self.assertTrue(
            prepare_terminal_marker_fail_closed(prepare),
            msg=(
                "Terminal completeness and exact required-ID set equality must fail closed "
                "through rollback before marker authorization"
            ),
        )
        self.assertLess(terminal_validation.end(), marker_position)
        rollback_cleanup_patterns = (
            r"(?s)(?:let|guard\s+let)\s+(?P<orphaned>[A-Za-z_]\w*)\s*=.*?"
            r"rollbackConsumableMediaReservation\(.*?mediaStore\.removeArchivedFiles\("
            r"(?P=orphaned)(?:\.orphanedMedia)?\)",
            r"(?s)rollbackConsumableMediaReservation\(.*?\|>\s*(?:map|mapToSignal)\s*\{\s*"
            r"(?P<orphaned>[A-Za-z_]\w*)\s+in.*?mediaStore\.removeArchivedFiles\("
            r"(?P=orphaned)(?:\.orphanedMedia)?\)",
        )
        self.assertTrue(
            any(re.search(pattern, prepare) for pattern in rollback_cleanup_patterns),
            msg="Only rollback-returned unreferenced records may flow to physical blob cleanup",
        )
        self.assertNotContains(
            around(prepare, "mediaStore.removeArchivedFiles(", 200, 300),
            "insertedResourceIds",
        )

    def test_prepare_revalidates_fresh_media_before_marker_write(self) -> None:
        prepare = swift_block(
            source("submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"),
            "public func prepareConsumableMedia(",
        )
        marker_calls = swift_calls(prepare, "GRVMPreservedConsumableMediaAttribute")
        self.assertTrue(marker_calls)
        marker_call = marker_calls[-1]
        marker_position = prepare.rfind(marker_call)
        attach_start = prepare.rfind("return self.postbox.transaction", 0, marker_position)
        self.assertGreaterEqual(attach_start, 0)
        attach_and_rollback = prepare[attach_start:]

        self.assertMatches(
            attach_and_rollback,
            r"(?s)guard\b.*?\blet\s+(?P<freshIds>[A-Za-z_]\w*)\s*=\s*"
            r"grvmPrimaryMediaResourceIds\(freshMessage\.media\).*?"
            r"Set\((?P=freshIds)\)\s*==\s*Set\(requiredPrimaryIds\).*?"
            r"else\s*\{\s*return\s+false",
        )
        self.assertContains(marker_call, "media: freshMessage.media")
        self.assertNotContains(marker_call, "media: preparation.message.media")
        self.assertOrdered(
            attach_and_rollback,
            "grvmPrimaryMediaResourceIds(freshMessage.media)",
            "GRVMPreservedConsumableMediaAttribute(",
            "if !attached",
            "rollbackConsumableMediaReservation(",
        )

    def test_store_reservation_is_sentinel_idempotent_and_fail_closed(self) -> None:
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        reservation = swift_block(store, "public func reserveConsumableMedia(")
        rollback = swift_block(store, "public func rollbackConsumableMediaReservation(")
        sentinel = re.search(
            r"(?:private\s+)?(?:static\s+)?let\s+(?P<name>[A-Za-z_]\w*)\s*:\s*Int64\s*=\s*-1\b",
            store,
        )
        self.assertIsNotNone(sentinel, msg="The consumable reservation must own an exact Int64 -1 sentinel")
        sentinel_name = sentinel.group("name")
        self.assertContainsAll(
            reservation,
            "self.transaction(database)",
            "executePrepared",
            sentinel_name,
            "insertedResourceIds",
            "sqlite3_changes(database)",
            ".complete",
            "byteCount > 0",
            "admitMedia",
        )
        reservation_mapping_calls = [
            call
            for call in swift_calls(reservation, "executePrepared")
            if "INSERT OR IGNORE INTO archived_message_media" in prepared_call_sql(call, store)
        ]
        self.assertEqual(1, len(reservation_mapping_calls))
        reservation_mapping_call = reservation_mapping_calls[0]
        reservation_sql = prepared_call_sql(reservation_mapping_call, store)
        for column in (
            "account_id",
            "peer_id",
            "message_namespace",
            "message_id",
            "thread_id",
            "revision_id",
            "resource_id",
        ):
            self.assertContains(reservation_sql, column)
        self.assertRegex(
            reservation_mapping_call,
            rf"(?s)self\.keyValues\(key\).*?(?:Self\.)?{re.escape(sentinel_name)}.*?resourceId",
        )
        self.assertMatches(
            reservation,
            r"(?s)sqlite3_changes\(database\).*?"
            r"insertedResourceIds\.insert\([^)]*resourceId",
        )
        self.assertNotContains(
            around(reservation, "INSERT OR IGNORE INTO archived_message_media", 0, 1800),
            "revisionId: 0",
        )
        reuse_gate = re.search(
            r"if let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=.*?"
            r"\1\.copyState\s*==\s*\.complete.*?\1\.byteCount\s*>\s*0",
            reservation,
            re.DOTALL,
        )
        self.assertIsNotNone(reuse_gate, msg="Reservation must branch on a valid complete blob")
        reuse_branch = swift_block(reservation, reuse_gate.group(0))
        self.assertNotContains(reuse_branch, "admitMedia")
        self.assertAnyContains(reuse_branch, "continue", "return")
        self.assertOrdered(reservation, reuse_branch, "admitMedia")
        self.assertContainsAll(
            rollback,
            "insertedResourceIds",
            sentinel_name,
            "executePrepared",
            "references == 0",
        )
        rollback_loop = re.search(
            r"(?:for\s+(?P<for_id>[A-Za-z_]\w*)\s+in\s+insertedResourceIds|"
            r"insertedResourceIds\.(?:forEach|map)\s*\{\s*(?P<closure_id>[A-Za-z_]\w*)\s+in)",
            rollback,
        )
        self.assertIsNotNone(rollback_loop, msg="Rollback must iterate only attempt-owned inserted IDs")
        rollback_resource = rollback_loop.group("for_id") or rollback_loop.group("closure_id")
        rollback_loop_block, _ = swift_block_at(rollback, rollback_loop.start())
        rollback_delete_calls = [
            call
            for call in swift_calls(rollback_loop_block, "executePrepared")
            if "DELETE FROM archived_message_media" in prepared_call_sql(call, store)
        ]
        self.assertEqual(1, len(rollback_delete_calls))
        rollback_delete_call = rollback_delete_calls[0]
        rollback_delete_sql = prepared_call_sql(rollback_delete_call, store)
        self.assertContains(rollback_delete_sql, "revision_id = ?")
        self.assertNotContains(rollback_delete_sql, "revision_id = 0")
        for predicate in (
            "account_id = ?",
            "peer_id = ?",
            "message_namespace = ?",
            "message_id = ?",
            "thread_id = ?",
            "resource_id = ?",
        ):
            self.assertContains(rollback_delete_sql, predicate)
        self.assertTrue(
            exact_sentinel_delete_call(
                rollback_delete_call,
                store,
                key_expression="key",
                sentinel_name=sentinel_name,
                resource_expression=rollback_resource,
            ),
            msg=(
                "Rollback DELETE must bind keyValues(key), the exact sentinel, "
                "and only the attempt-owned resource ID"
            ),
        )
        resolved_loop_sql = [
            prepared_call_sql(call, store)
            for call in swift_calls(rollback_loop_block, "executePrepared")
        ]
        self.assertTrue(
            any("SELECT COUNT(*) FROM archived_message_media" in sql for sql in resolved_loop_sql)
        )
        self.assertContains(rollback_loop_block, "references == 0")
        self.assertTrue(
            any("DELETE FROM archived_media_blobs" in sql for sql in resolved_loop_sql)
        )
        self.assertAnyContains(rollback_loop_block, "orphanedMedia", "removableMedia", "removedMedia")

    def test_save_deleted_transfers_sentinel_after_revision_zero_mapping(self) -> None:
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        save_deleted = swift_block(
            store,
            "public func saveDeleted(",
        )
        sentinel = re.search(
            r"(?:private\s+)?(?:static\s+)?let\s+(?P<name>[A-Za-z_]\w*)\s*:\s*Int64\s*=\s*-1\b",
            store,
        )
        self.assertIsNotNone(sentinel)
        sentinel_name = sentinel.group("name")
        self.assertContainsAll(
            save_deleted,
            "self.transaction(database)",
            "insertMapping(database, key: message.key, revisionId: 0",
            sentinel_name,
            "executePrepared",
        )
        transfer_loop = re.search(
            r"for\s+(?P<record>[A-Za-z_]\w*)\s+in\s+[A-Za-z_]\w*\s*\{(?s:.*?)"
            r"insertMapping\(database,\s*key:\s*message\.key,\s*revisionId:\s*0",
            save_deleted,
        )
        self.assertIsNotNone(transfer_loop, msg="Sentinel transfer must be scoped to the saved media loop")
        transfer_resource = transfer_loop.group("record")
        transfer_loop_block, _ = swift_block_at(save_deleted, transfer_loop.start())
        transfer_delete_calls = [
            call
            for call in swift_calls(transfer_loop_block, "executePrepared")
            if "DELETE FROM archived_message_media" in prepared_call_sql(call, store)
        ]
        self.assertEqual(1, len(transfer_delete_calls))
        transfer_call = transfer_delete_calls[0]
        transfer_sql = prepared_call_sql(transfer_call, store)
        self.assertContains(transfer_sql, "revision_id = ?")
        self.assertNotContains(transfer_sql, "revision_id = 0")
        self.assertTrue(
            exact_sentinel_delete_call(
                transfer_call,
                store,
                key_expression="message.key",
                sentinel_name=sentinel_name,
                resource_expression=f"{transfer_resource}.resourceId",
            ),
            msg=(
                "Sentinel transfer DELETE must bind the exact saved message key, -1 revision, "
                "and the revision-0 record resource"
            ),
        )
        self.assertLess(
            transfer_loop_block.find("insertMapping(database, key: message.key, revisionId: 0"),
            transfer_loop_block.find(transfer_call),
        )

    def test_cleanup_reference_queries_count_sentinel_and_normal_mappings(self) -> None:
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        matches = list(
            re.finditer(
                r"SELECT COUNT\(\*\) FROM archived_message_media WHERE account_id = \? AND resource_id = \?",
                store,
            )
        )
        self.assertGreaterEqual(len(matches), 2)
        for match in matches:
            reference_query = store[max(0, match.start() - 200) : match.end() + 200]
            self.assertNotContains(reference_query, "revision_id")
        finalize = swift_block(store, "public func finalizeDeletedCleanup(")
        self.assertContains(finalize, "DELETE FROM archived_message_media")
        self.assertContains(finalize, "revision_id = 0")
        self.assertContains(finalize, "references == 0")
        self.assertContains(store, "if references == 0")

    def test_restore_requires_exact_complete_mapping_and_fresh_postbox_write(self) -> None:
        good_records = (
            ArchivedMediaRecord("account-a", "message-1", "photo-z", restored_size=10),
            ArchivedMediaRecord("account-a", "message-1", "file-a", restored_size=20),
        )
        self.assertTrue(
            restore_authorized(
                account="account-a",
                message_key="message-1",
                marker_ids=("photo-z", "file-a"),
                records=good_records,
            )
        )
        for invalid in (
            (),
            good_records[:1],
            good_records + (ArchivedMediaRecord("account-a", "message-1", "extra"),),
            (ArchivedMediaRecord("account-b", "message-1", "photo-z"), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "other-message", "photo-z"), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "message-1", "photo-z", complete=False), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "message-1", "photo-z", byte_count=0), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "message-1", "photo-z", restored_size=0), ArchivedMediaRecord("account-a", "message-1", "file-a")),
        ):
            self.assertFalse(
                restore_authorized(
                    account="account-a",
                    message_key="message-1",
                    marker_ids=("photo-z", "file-a"),
                    records=invalid,
                )
            )
        restore = swift_block(
            source("submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"),
            "public func restoreArchivedMedia(",
        )
        media_store_restore = swift_block(
            source("submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"),
            "public func restore(",
        )
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        mapping_lookup = swift_block(store, "public func consumableMedia(")
        self.assertContainsAll(
            mapping_lookup,
            "consumableMediaRevisionId",
            "archived_message_media",
            "archived_media_blobs",
            "account_id = ?",
            "peer_id = ?",
            "message_namespace = ?",
            "message_id = ?",
            "thread_id = ?",
            "revision_id = ?",
            "resource_id",
        )
        self.assertContainsAll(
            restore,
            "public func restoreArchivedMedia(for message: Message) -> Signal<Bool, NoError>",
            "consumableMedia(key:",
            "self.messageKey(",
            "accountRecordId",
            "transaction.getMessage(message.id)",
            "stableId",
            "Set(",
            "context.resourceIds",
            "==",
            ".complete",
            "byteCount > 0",
            "mediaStore.restore(",
            "MediaResourceId",
            "completedResourcePath",
            "attribute.media",
            "transaction.updateMessage",
        )
        self.assertContainsAll(
            media_store_restore,
            "MediaResourceId(record.resourceId)",
            "restoreResourceData",
        )
        restore_calls = swift_calls(restore, "mediaStore.restore")
        self.assertGreaterEqual(len(restore_calls), 1)
        restore_loop = re.search(
            r"(?:for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+records|"
            r"records\.(?:map|compactMap)\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s+in)",
            restore,
        )
        if restore_loop is not None:
            record_name = restore_loop.group(1) or restore_loop.group(2)
            for restore_call in restore_calls:
                self.assertContains(restore_call, record_name)
        else:
            self.assertContains(restore, "records.map")
            for restore_call in restore_calls:
                self.assertContains(restore_call, "$0")
        self.assertMatches(
            restore,
            r"(?s)(?:allSatisfy|\.all\s*\{).*?\.complete.*?(?:byteCount|size)\s*>\s*0",
        )
        set_comparison = around(restore, "attribute.resourceIds", 600, 1200)
        self.assertContainsAll(set_comparison, "Set(", "records", "==")
        row_bindings = list(
            re.finditer(
                r"(?:guard\s+let|if\s+let|let)\s+(?P<row>[A-Za-z_]\w*)\s*=\s*"
                r"transaction\.getMessage\(message\.id\)",
                restore,
            )
        )
        self.assertGreaterEqual(len(row_bindings), 2)
        first_row = row_bindings[0].group("row")
        fresh_row = row_bindings[-1].group("row")
        for row_name in (first_row, fresh_row):
            self.assertRegex(
                restore,
                rf"(?s){re.escape(row_name)}\.stableId\s*==\s*message\.stableId|"
                rf"message\.stableId\s*==\s*{re.escape(row_name)}\.stableId",
            )
        self.assertRegex(
            restore,
            rf"(?s){re.escape(first_row)}\.attributes.*?GRVMPreservedConsumableMediaAttribute",
        )
        records_binding = re.search(
            r"guard\s+let\s+(?P<records>[A-Za-z_]\w*)\s*=\s*try\?\s*"
            r"self\.store\.consumableMedia\(key:",
            restore,
            re.DOTALL,
        )
        self.assertIsNotNone(records_binding, msg="Restore must bind exact message mappings")
        records_name = records_binding.group("records")
        self.assertRegex(
            restore,
            rf"(?s)Set\(\s*context\.resourceIds\s*\)\s*==\s*"
            rf"Set\(\s*{re.escape(records_name)}\.(?:map|compactMap).*?resourceId.*?\)|"
            rf"Set\(\s*{re.escape(records_name)}\.(?:map|compactMap).*?resourceId.*?\)\s*==\s*"
            r"Set\(\s*context\.resourceIds\s*\)",
        )
        self.assertLess(restore.find("mediaStore.restore("), restore.rfind("completedResourcePath"))
        self.assertLess(
            restore.rfind("completedResourcePath"),
            restore.rfind("transaction.getMessage(message.id)"),
        )
        self.assertLess(
            restore.rfind("transaction.getMessage(message.id)"),
            restore.rfind("transaction.updateMessage"),
        )
        path_window = around(restore, "completedResourcePath", 1600, 1600)
        self.assertAnyContains(path_window, "guard", "if")
        self.assertAnyContains(path_window, "return false", ".single(false)", "putNext(false)")
        direct_path_failure = re.search(
            r"(?s)(?:guard|if)(?:(?!transaction\.updateMessage).)*?"
            r"completedResourcePath(?:(?!transaction\.updateMessage).)*?"
            r"(?:else\s*)?\{(?:(?!transaction\.updateMessage).)*?"
            r"(?:return\s+false|\.single\(false\)|putNext\(false\))",
            restore,
        )
        bound_path_failure = re.search(
            r"(?s)(?:let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"(?:(?!transaction\.updateMessage).)*?completedResourcePath.*?"
            r"guard\s+\1\s+else\s*\{.*?"
            r"(?:return\s+false|\.single\(false\)|putNext\(false\))",
            restore,
        )
        self.assertIsNotNone(
            direct_path_failure or bound_path_failure,
            msg="Every restore path must fail before the Postbox marker update",
        )
        self.assertNotContains(
            path_window[: path_window.find("completedResourcePath")],
            "transaction.updateMessage",
        )
        update_tail = restore[restore.rfind("transaction.updateMessage") - 2500 :]
        self.assertContains(update_tail, fresh_row)
        self.assertAnyContains(update_tail, "attribute.media", "replacementMedia")
        self.assertNotContains(restore, "archivedMedia(accountId:")
        for forbidden in ("network.request", "fetchedResource", "resourceData(", "fetchResource"):
            self.assertNotContains(restore, forbidden)

    def test_restore_filters_deleted_revision_extras_to_marker_resource_ids(self) -> None:
        records = (
            ArchivedMediaRecord("account-a", "message-1", "primary", restored_size=10),
            ArchivedMediaRecord("account-a", "message-1", "preview", restored_size=5),
        )
        marker_ids = {"primary"}
        filtered = tuple(record for record in records if record.resource_id in marker_ids)
        self.assertTrue(
            restore_authorized(
                account="account-a",
                message_key="message-1",
                marker_ids=tuple(marker_ids),
                records=filtered,
            )
        )

        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        lookup = swift_block(store, "public func consumableMedia(")
        restore = swift_block(
            source("submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"),
            "public func restoreArchivedMedia(",
        )
        self.assertContains(lookup, "resourceIds: Set<String>")
        self.assertMatches(
            lookup,
            r"(?s)(?:filter|compactMap).*?resourceIds\.contains\(.*?resourceId",
        )
        lookup_calls = swift_calls(restore, "consumableMedia")
        self.assertEqual(1, len(lookup_calls))
        self.assertContains(lookup_calls[0], "resourceIds: Set(context.resourceIds)")
        self.assertOrdered(
            restore,
            "transaction.getMessage(message.id)",
            "consumableMedia(",
            "mediaStore.restore(",
        )

    def test_restore_supports_deleted_revision_zero_without_authorizing_replay(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
        )
        restore = swift_block(coordinator, "public func restoreArchivedMedia(")
        context = swift_block(coordinator, "private struct GRVMConsumableMediaRestoreContext")
        replay = swift_block(
            source("submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"),
            "func grvmCanReplayMessage(",
        )

        self.assertContainsAll(
            context,
            "resourceIds: [String]",
            "requiresConsumableMarker: Bool",
        )
        self.assertContainsAll(
            restore,
            "GRVMPreservedConsumableMediaAttribute",
            "GRVMDeletedMessageAttribute",
            "grvmPrimaryMediaResourceIds(",
            "deletedAttribute.resourceIds",
            "isSubset(of:",
            "resourceIds: Set(context.resourceIds)",
        )
        self.assertGreaterEqual(
            restore.count("grvmPrimaryMediaResourceIds("),
            2,
            msg="Deleted restore must revalidate primary IDs on both the initial and fresh Postbox rows",
        )
        self.assertMatches(
            restore,
            r"(?s)GRVMPreservedConsumableMediaAttribute.*?"
            r"resourceIds:\s*attribute\.resourceIds.*?"
            r"requiresConsumableMarker:\s*true",
        )
        self.assertMatches(
            restore,
            r"(?s)GRVMDeletedMessageAttribute.*?"
            r"resourceIds:\s*primaryResourceIds.*?"
            r"requiresConsumableMarker:\s*false",
        )
        self.assertMatches(
            restore,
            r"(?s)if\s+context\.requiresConsumableMarker.*?"
            r"replacementMedia\s*=\s*attribute\.media.*?"
            r"else.*?replacementMedia\s*=\s*nil",
        )
        self.assertContains(replay, "GRVMPreservedConsumableMediaAttribute")
        self.assertNotContains(replay, "GRVMDeletedMessageAttribute")


class ReplayLocalForwardUIContractTests(SourceContractTestCase):
    def test_burn_eligibility_fixture_covers_every_exclusion(self) -> None:
        eligible = BurnCase()
        self.assertTrue(burn_eligible(eligible))
        for peer in ("user", "group", "channel"):
            for media in ("image", "file"):
                self.assertTrue(burn_eligible(replace(eligible, peer=peer, media=media)))
        exclusions = {
            "multi": {"count": 2},
            "outgoing": {"incoming": False},
            "ordinary": {"ttl": False},
            "consumed": {"consumed": True},
            "noAttribute": {"has_consumable": False},
            "local": {"namespace": "local"},
            "scheduled": {"namespace": "scheduled"},
            "secret": {"peer": "secret"},
            "poll": {"media": "poll"},
            "action": {"media": "action"},
        }
        for name, changes in exclusions.items():
            with self.subTest(name=name):
                self.assertFalse(burn_eligible(replace(eligible, **changes)))
        self.assertEqual("consume:force", burn_execution_steps(True)[-1])
        self.assertEqual("consume:force", burn_execution_steps(False)[-1])
        expected_events = (
            ("prepare", "account-a", "message-7"),
            ("consume:force", "account-a", "message-7"),
        )
        for prepared in (False, True):
            self.assertEqual(
                expected_events,
                burn_execution_events(
                    eligible=True,
                    confirmed=True,
                    prepared=prepared,
                    account="account-a",
                    message_id="message-7",
                ),
            )
        self.assertEqual(
            (),
            burn_execution_events(
                eligible=True,
                confirmed=False,
                prepared=True,
                account="account-a",
                message_id="message-7",
            ),
        )

    def test_burn_source_has_irreversible_truth_table_and_one_forced_call(self) -> None:
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        eligibility = swift_without_comments(swift_block(context_menu, "func grvmCanBurnMessage("))
        action = swift_without_comments(swift_block(context_menu, "func grvmBurnMessage("))
        burn_item, burn_item_action = action_item_containing(context_menu, "grvmBurnMessage")
        self.assertContainsAll(
            eligibility,
            "messages.count == 1",
            "Namespaces.Message.Cloud",
            "Namespaces.Peer.CloudUser",
            "Namespaces.Peer.CloudGroup",
            "Namespaces.Peer.CloudChannel",
            ".Incoming",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "ConsumableContentMessageAttribute",
            "!attribute.consumed",
            "minAutoremoveOrClearTimeout",
        )
        selected_binding = re.search(
            r"(?:guard\s+messages\.count\s*==\s*1[^\n]*|if\s+messages\.count\s*==\s*1[^\n]*|"
            r"let\s+(?P<name>[A-Za-z_]\w*)\s*=\s*messages\[0\])",
            eligibility,
        )
        self.assertIsNotNone(selected_binding, msg="Burn eligibility must structurally bind one selected message")
        self.assertTrue(burn_item_action, msg="Burn menu item must be located by its semantic handler")
        self.assertContains(burn_item_action, "grvmBurnMessage")
        item_position = context_menu.find(burn_item)
        item_prefix = context_menu[max(0, item_position - 2500) : item_position]
        item_message = re.search(
            r"let\s+(?P<message>[A-Za-z_]\w*)\s*=\s*messages\[0\]",
            item_prefix,
        )
        self.assertIsNotNone(item_message, msg="The Burn row must capture the exact selected message")
        self.assertContains(item_prefix, "messages.count == 1")
        self.assertRegex(
            burn_item_action,
            rf"grvmBurnMessage\([^)]*{re.escape(item_message.group('message'))}",
        )
        self.assertContainsAll(
            action,
            "textAlertController",
            "destructiveAction",
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
            "force: true",
        )
        self.assertRegex(action, r"func\s+grvmBurnMessage\([^)]*message\s*:\s*Message")
        prepare_calls = swift_calls(action, "prepareConsumableMedia")
        self.assertEqual(1, len(prepare_calls))
        self.assertRegex(
            prepare_calls[0],
            r"(?s)context\.account\.peerId\s*,\s*message\b",
        )
        forced_calls = [
            call
            for call in swift_calls(action, "markMessageContentAsConsumedInteractively")
            if "force: true" in call
        ]
        self.assertEqual(1, len(forced_calls))
        self.assertRegex(forced_calls[0], r"messageId\s*:\s*message\.id\b")
        self.assertOrdered(
            action,
            "textAlertController",
            "destructiveAction",
            "prepareConsumableMedia",
            "force: true",
        )
        confirmation_candidates = [
            call
            for call in swift_calls(action, "TextAlertAction")
            if "destructiveAction" in call and "force: true" in call
        ]
        self.assertEqual(1, len(confirmation_candidates))
        confirmation = confirmation_candidates[0]
        self.assertContainsAll(
            confirmation,
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
            "force: true",
        )
        self.assertTrue(
            burn_confirmation_ignores_prepare_bool(confirmation),
            msg="Confirmed Burn must ignore prepare Bool and always enqueue the same forced consume",
        )
        alert_call = next(
            (call for call in swift_calls(action, "textAlertController") if "destructiveAction" in call),
            "",
        )
        self.assertTrue(alert_call)
        self.assertEqual(1, action.count("force: true"))
        force_sites: list[str] = []
        force_pattern = re.compile(
            r"markMessageContentAsConsumedInteractively\(\s*"
            r"messageId:[^)]*?force:\s*true\s*\)",
            re.DOTALL,
        )
        for path in (ROOT / "submodules").rglob("*.swift"):
            text = path.read_text(encoding="utf-8")
            if force_pattern.search(text):
                force_sites.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            ["submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"],
            force_sites,
        )

    def test_task9_and_task10_public_copy_uses_typed_selected_language_strings(self) -> None:
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        forward = source(
            "submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift"
        )
        burn = swift_block(context_menu, "func grvmBurnMessage(")
        replay = swift_block(context_menu, "func grvmReplayMessage(")
        burn_item, _ = action_item_containing(context_menu, "grvmBurnMessage")
        replay_item, _ = action_item_containing(context_menu, "grvmReplayMessage")
        local_copy_item, _ = action_item_containing(
            context_menu, "grvmForwardLocalCopy"
        )
        read_item, _ = action_item_containing(context_menu, "grvmApplyMaxReadIndex")

        self.assertContainsAll(
            burn,
            "GRVMgramStrings(presentationData.strings)",
            "strings[.burnTitle]",
            "strings[.burnText]",
            "strings[.burnAction]",
        )
        self.assertContainsAll(
            replay,
            "GRVMgramStrings(presentationData.strings)",
            "strings[.replayRestoreFailed]",
        )
        self.assertContains(burn_item, "grvmStrings[.menuBurn]")
        self.assertContains(replay_item, "grvmStrings[.menuReplay]")
        self.assertContains(
            local_copy_item, "grvmStrings[.menuForwardLocalCopy]"
        )
        self.assertContains(read_item, "grvmStrings[.menuReadMessage]")
        self.assertContainsAll(
            forward,
            "GRVMgramStrings(self.presentationData.strings)",
            "grvmStrings[.forwardLocalCopyUnsupported]",
            "grvmStrings[.forwardLocalCopyUnavailable]",
        )

        combined = context_menu + forward
        for literal in (
            '"Burn media?"',
            '"This permanently marks the media as viewed on Telegram."',
            '"Burn"',
            '"Preserved media is unavailable."',
            '"Replay"',
            '"Forward Local Copy"',
            '"Read Message"',
            '"This message can\'t be forwarded as a local copy."',
            '"The local media is unavailable."',
        ):
            self.assertNotContains(combined, literal)

    def test_replay_fixture_keeps_normal_receipts_and_disables_every_replay_edge(self) -> None:
        self.assertTrue(all(replay_flow(True).values()))
        self.assertFalse(any(replay_flow(False).values()))
        self.assertEqual(
            [True, True, False, True],
            [
                should_consume_playback(consume_view_once=consume, is_view_once=is_view_once)
                for consume, is_view_once in ((True, True), (True, False), (False, True), (False, False))
            ],
        )
        self.assertEqual("hidden", replay_ui_outcome(eligibility_restore=False, tap_restore=True, fresh_row=True))
        self.assertEqual("unavailable-alert", replay_ui_outcome(eligibility_restore=True, tap_restore=False, fresh_row=True))
        self.assertEqual("unavailable-alert", replay_ui_outcome(eligibility_restore=True, tap_restore=True, fresh_row=False))
        self.assertEqual("open-fresh-without-consume", replay_ui_outcome(eligibility_restore=True, tap_restore=True, fresh_row=True))
        self.assertTrue(replay_eligible(ReplayCase(consumed=True)))
        self.assertTrue(replay_eligible(ReplayCase(consumed=False, expired=True)))
        self.assertTrue(replay_eligible(ReplayCase(consumed=False, locally_deleted=True)))
        for invalid in (
            ReplayCase(count=2),
            ReplayCase(has_marker=False),
            ReplayCase(consumed=False),
            ReplayCase(restored=False),
        ):
            self.assertFalse(replay_eligible(invalid))

    def test_replay_flag_propagates_through_gallery_and_playlist(self) -> None:
        interaction = source(
            "submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift"
        )
        account_open = source("submodules/AccountContext/Sources/OpenChatMessage.swift")
        chat_controller = source("submodules/TelegramUI/Sources/ChatController.swift")
        open_chat = source("submodules/TelegramUI/Sources/OpenChatMessage.swift")
        gallery_data = source("submodules/GalleryData/Sources/GalleryData.swift")
        secret_preview = source(
            "submodules/GalleryUI/Sources/SecretMediaPreviewController.swift"
        )
        playlist = source(
            "submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift"
        )
        playlist_item = swift_block(playlist, "public final class MessageMediaPlaylistItem")

        open_message_params = swift_block(interaction, "public struct OpenMessageParams")
        self.assertContainsAll(
            open_message_params,
            "consumeOnOpen: Bool",
            "consumeOnOpen: Bool = true",
            "self.consumeOnOpen = consumeOnOpen",
        )
        self.assertContainsAll(
            account_open,
            "public let consumeOnOpen: Bool",
            "consumeOnOpen: Bool = true",
            "self.consumeOnOpen = consumeOnOpen",
        )
        self.assertContains(chat_controller, "consumeOnOpen: params.consumeOnOpen")
        self.assertGreaterEqual(open_chat.count("params.consumeOnOpen"), 2)
        self.assertContains(open_chat, "consumeOnOpen: params.consumeOnOpen")
        self.assertContains(open_chat, "consumeViewOnce: params.consumeOnOpen")
        self.assertContainsAll(
            gallery_data,
            "consumeOnOpen: Bool = true",
            "SecretMediaPreviewController(context: context, messageId: message.id, consumeOnOpen: consumeOnOpen)",
        )
        self.assertContainsAll(
            secret_preview,
            "private let consumeOnOpen: Bool",
            "consumeOnOpen: Bool = true",
            "self.consumeOnOpen = consumeOnOpen",
        )
        self.assertContainsAll(
            playlist,
            "consumeViewOnce: Bool = true",
            "self.consumeViewOnce = consumeViewOnce",
            "consumeViewOnce",
        )
        self.assertContainsAll(
            playlist_item,
            "consumeViewOnce",
            "isViewOnce:",
        )
        item_constructions = [
            call
            for call in swift_calls(playlist, "MessageMediaPlaylistItem")
            if "message:" in call
        ]
        self.assertGreaterEqual(len(item_constructions), 3)
        for construction in item_constructions:
            self.assertContains(construction, "consumeViewOnce: self.consumeViewOnce")
        item_calls = swift_calls(playlist_item, "SharedMediaPlaybackDataSource.telegramFile")
        self.assertTrue(item_calls)
        for call in item_calls:
            call_position = playlist_item.find(call)
            view_once_argument = swift_top_level_argument(call, "isViewOnce")
            self.assertTrue(
                view_once_argument,
                msg="Every playback data-source call must bind isViewOnce explicitly",
            )
            self.assertTrue(
                is_exact_view_once_expression(
                    resolve_swift_boolean_alias(
                        playlist_item,
                        view_once_argument,
                        before=call_position,
                    )
                ),
                msg=(
                    "isViewOnce must be exactly consumeViewOnce && "
                    "timeout == viewOnceTimeout, without trailing logic"
                ),
            )

    def test_replay_voice_playlist_is_scoped_to_the_exact_message(self) -> None:
        open_chat = source("submodules/TelegramUI/Sources/OpenChatMessage.swift")
        start = open_chat.find("case let .audio(file):")
        end = open_chat.find("case let .story(", start)
        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)
        audio = open_chat[start:end]
        replay_branch = swift_block(audio, "if !params.consumeOnOpen")
        self.assertContainsAll(
            replay_branch,
            "!params.consumeOnOpen",
            ".singleMessage(params.message.id)",
        )
        self.assertNotContains(replay_branch, ".messages(")
        self.assertOrdered(
            audio,
            "if !params.consumeOnOpen",
            ".singleMessage(params.message.id)",
            "consumeViewOnce: params.consumeOnOpen",
        )

    def test_replay_receipt_gates_prepare_and_consume_only_on_normal_open(self) -> None:
        secret_preview = source(
            "submodules/GalleryUI/Sources/SecretMediaPreviewController.swift"
        )
        playlist = source(
            "submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift"
        )
        apply_view = swift_block(secret_preview, "private func applyMessageView()")
        playback_started = swift_block(playlist, "public func onItemPlaybackStarted(")
        self.assertContainsAll(
            apply_view,
            "consumeOnOpen",
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
        )
        positive_open = re.search(r"if\s+(?:self\.)?consumeOnOpen\s*\{", apply_view)
        positive_open_block = (
            swift_block_at(apply_view, positive_open.start())[0]
            if positive_open is not None
            else ""
        )
        negative_open = re.search(
            r"guard\s+(?:self\.)?consumeOnOpen\s+else\s*\{",
            apply_view,
        )
        negative_open_block = (
            swift_block_at(apply_view, negative_open.start())[0]
            if negative_open is not None
            else ""
        )
        self.assertTrue(
            (
                "prepareConsumableMedia" in positive_open_block
                and "markMessageContentAsConsumedInteractively" in positive_open_block
            )
            or (
                "return" in negative_open_block
                and apply_view.find("prepareConsumableMedia", negative_open.start() + len(negative_open_block)) >= 0
                and apply_view.find(
                    "markMessageContentAsConsumedInteractively",
                    negative_open.start() + len(negative_open_block),
                )
                >= 0
            ),
            msg="Normal preview may prepare and consume; replay's false branch must do neither",
        )
        self.assertEqual(1, apply_view.count("markMessageContentAsConsumedInteractively"))
        self.assertLess(
            apply_view.find("prepareConsumableMedia"),
            apply_view.find("markMessageContentAsConsumedInteractively"),
        )
        self.assertNotContains(apply_view, "force: true")
        self.assertContainsAll(
            playback_started,
            "consumeViewOnce",
            "viewOnceTimeout",
            "markMessageContentAsConsumedInteractively",
        )
        self.assertTrue(
            call_is_owned_by_exact_receipt_gate(
                playback_started,
                "markMessageContentAsConsumedInteractively",
            ),
            msg=(
                "Playback receipts must be owned by the exact consumeViewOnce || "
                "timeout != viewOnceTimeout polarity (or its exact fail-closed inversion)"
            ),
        )
        self.assertNotContains(playback_started, "force: true")
        self.assertEqual(1, playback_started.count("markMessageContentAsConsumedInteractively"))

    def test_reservation_and_preview_receipt_outlive_ui_disposal(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
        )
        helper = swift_block(coordinator, "private func grvmNonCancellable")
        prepare = swift_block(coordinator, "public func prepareConsumableMedia(")
        self.assertContainsAll(
            helper,
            "Signal<T, NoError>",
            "signal.startStandalone(",
            "next: subscriber.putNext",
            "completed: subscriber.putCompletion",
            "return EmptyDisposable",
        )
        durable_calls = swift_calls(prepare, "grvmNonCancellable")
        self.assertEqual(1, len(durable_calls))
        durable = durable_calls[0]
        self.assertContainsAll(
            durable,
            "combineLatest(archiveSignals)",
            "store.updateMedia(",
            "rollbackConsumableMediaReservation(",
            "postbox.transaction",
            "GRVMPreservedConsumableMediaAttribute(",
        )
        self.assertLess(
            prepare.find("reserveConsumableMedia("),
            prepare.find(durable_calls[0]),
        )

        preview = source("submodules/GalleryUI/Sources/SecretMediaPreviewController.swift")
        apply_view = swift_block(preview, "private func applyMessageView()")
        receipt_gate = swift_block(apply_view, "if self.consumeOnOpen")
        self.assertContainsAll(
            receipt_gate,
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
            "startStandalone()",
        )
        self.assertNotContains(receipt_gate, "[weak self]")
        self.assertNotContains(preview, "markMessageAsConsumedDisposable")

    def test_replay_restore_is_rechecked_and_opens_a_fresh_message(self) -> None:
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        eligibility = swift_block(context_menu, "func grvmCanReplayMessage(")
        replay_item, replay_action = action_item_containing(context_menu, "grvmReplayMessage")
        replay_handler = swift_block(context_menu, "func grvmReplayMessage(")
        if not replay_item:
            replay_item, replay_action = action_item_containing(
                context_menu, "consumeOnOpen: false"
            )
        replay = replay_handler or replay_action
        self.assertContainsAll(
            eligibility,
            "Signal<Bool, NoError>",
            "messages.count == 1",
            "GRVMPreservedConsumableMediaAttribute",
            "ConsumableContentMessageAttribute",
            "attribute.consumed",
            "TelegramMediaExpiredContent",
            "isLocallyDeletedMessage",
            "restoreConsumableMedia",
            "accountPeerId",
        )
        self.assertNotContains(eligibility, ".single(true)")
        eligibility_restore_calls = swift_calls(eligibility, "restoreConsumableMedia")
        self.assertEqual(1, len(eligibility_restore_calls))
        self.assertRegex(
            eligibility_restore_calls[0],
            r"(?s)accountPeerId\s*,\s*message\b",
        )
        self.assertContains(eligibility, ".single(false)")
        exact_account_callers = [
            call
            for call in swift_calls(context_menu, "grvmCanReplayMessage")
            if "context.account.peerId" in call
        ]
        self.assertTrue(exact_account_callers, msg="Replay eligibility must receive the account peer ID")
        self.assertTrue(replay_item, msg="Replay item must be found from its semantic behavior")
        gating_if = None
        for match in re.finditer(r"if\s+(?P<flag>[A-Za-z_]\w*)\s*\{", context_menu):
            block, _ = swift_block_at(context_menu, match.start())
            if replay_item in block:
                gating_if = match
                break
        self.assertIsNotNone(gating_if, msg="The Replay item must live inside its Bool eligibility branch")
        replay_flag = gating_if.group("flag")
        gate_prefix = context_menu[max(0, gating_if.start() - 9000) : gating_if.start()]
        self.assertContains(gate_prefix, "grvmCanReplayMessage(")
        self.assertRegex(
            gate_prefix,
            rf"(?s)\|>\s*(?:map|mapToSignal)\s*\{{[^\n{{}}]*\b{re.escape(replay_flag)}\b[^\n{{}}]*\bin\b",
            msg="The same Bool emitted by replay eligibility must gate row insertion",
        )
        self.assertContainsAll(
            replay,
            "GRVMPreservedConsumableMediaAttribute",
            "restoreConsumableMedia",
            "transaction.getMessage(message.id)",
            "consumeOnOpen: false",
            "controllerInteraction.openMessage",
        )
        tap_restore_calls = swift_calls(replay, "restoreConsumableMedia")
        self.assertEqual(1, len(tap_restore_calls))
        self.assertRegex(
            tap_restore_calls[0],
            r"(?s)context\.account\.peerId\s*,\s*message\b",
        )
        restore_position = replay.find(tap_restore_calls[0])
        restore_callback = re.search(
            r"(?:\.start(?:Standalone)?\s*\([^)]*next\s*:\s*\{|"
            r"\|>\s*(?:map|mapToSignal)\s*\{)\s*"
            r"(?P<result>[A-Za-z_]\w*)\s+in",
            replay[restore_position:],
            re.DOTALL,
        )
        self.assertIsNotNone(restore_callback, msg="Replay must bind the emitted restore Bool")
        restore_result = restore_callback.group("result")
        restore_guard = re.search(
            rf"guard\s+{re.escape(restore_result)}\s+else\s*\{{",
            replay[restore_position:],
        )
        self.assertIsNotNone(restore_guard, msg="Replay must fail closed after restore verification")
        guard_start = restore_position + restore_guard.start()
        failure_branch, _ = swift_block_at(replay, guard_start)
        self.assertContains(failure_branch, "return")
        self.assertRegex(failure_branch, r"(?:present|displayUndo|textAlertController)")
        self.assertNotContains(failure_branch, "openMessage")
        fresh_name = replay_fresh_row_fail_closed(replay)
        self.assertTrue(
            fresh_name,
            msg=(
                "Replay must reload the Postbox row and show an unavailable alert "
                "before returning when that fresh row is absent"
            ),
        )
        fresh_open_anchor = f"controllerInteraction.openMessage({fresh_name}"
        if fresh_open_anchor not in replay:
            fresh_open_anchor = f"controllerInteraction.openMessage(message: {fresh_name}"
        self.assertContains(replay, fresh_open_anchor)
        self.assertOrdered(
            replay,
            "restoreConsumableMedia",
            "guard " + restore_result + " else",
            "consumeOnOpen: false",
            fresh_open_anchor,
        )
    def test_local_copy_fixture_distinguishes_ready_unavailable_and_unsupported(self) -> None:
        cases = {
            "protectedText": (
                LocalCopyCase(source_protected=True, text="safe text"),
                "ready",
            ),
            "deletedImage": (
                LocalCopyCase(deleted=True, media=("image",), current_size=10),
                "ready",
            ),
            "restoredVoice": (
                LocalCopyCase(one_play=True, media=("file",), restored_size=20),
                "ready",
            ),
            "ordinary": (
                LocalCopyCase(media=("image",), current_size=10),
                "notCandidate",
            ),
            "poll": (
                LocalCopyCase(source_protected=True, media=("poll",)),
                "unsupported",
            ),
            "mixed": (
                LocalCopyCase(source_protected=True, media=("image", "poll"), current_size=10),
                "unsupported",
            ),
            "missingBytes": (
                LocalCopyCase(ttl=True, media=("file",)),
                "unavailable",
            ),
            "emptyText": (
                LocalCopyCase(chat_protected=True),
                "unsupported",
            ),
        }
        for name, (case, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(expected, local_copy_outcome(case))
        self.assertEqual(
            "producer-removes-temp",
            local_copy_temp_cleanup(("temp-created", "error")),
        )
        self.assertEqual(
            "stock-move-owns-cleanup",
            local_copy_temp_cleanup(("temp-created", "return-resource")),
        )

    def test_local_copy_availability_uses_marker_media_only_when_visible_media_expired(self) -> None:
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        eligibility = swift_block(context_menu, "func grvmCanForwardLocalCopy(")
        self.assertContainsAll(
            eligibility,
            "GRVMPreservedConsumableMediaAttribute",
            "TelegramMediaExpiredContent",
            "marker.media",
            "restoreConsumableMedia",
        )
        self.assertMatches(
            eligibility,
            r"(?s)if\s+message\.media\.contains.*?TelegramMediaExpiredContent.*?"
            r"media\s*=\s*marker\.media.*?else.*?media\s*=\s*message\.media",
        )
        self.assertRegex(
            eligibility,
            r"(?s)(?:if|guard)\s+let\s+image\s*=\s*media\[0\]\s+as\?\s+TelegramMediaImage",
        )
        self.assertNotContains(eligibility, "marker?.media ?? message.media")

    def test_local_copy_enqueue_reloads_fresh_row_before_selecting_marker_media(self) -> None:
        enqueue = swift_block(
            source("submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift"),
            "func GRVMPreservedMediaEnqueue(",
        )
        self.assertContainsAll(
            enqueue,
            "context.account.postbox.transaction",
            "transaction.getMessage(message.id)",
            "stableId == message.stableId",
            "TelegramMediaExpiredContent",
            "marker.media",
        )
        fresh_binding = re.search(
            r"guard\s+let\s+(?P<fresh>[A-Za-z_]\w*)\s*=\s*"
            r"transaction\.getMessage\(message\.id\).*?"
            r"(?P=fresh)\.stableId\s*==\s*message\.stableId",
            enqueue,
            re.DOTALL,
        )
        self.assertIsNotNone(
            fresh_binding,
            msg="Local-copy preparation must fail closed on a stale Postbox row",
        )
        fresh_name = fresh_binding.group("fresh")
        self.assertRegex(
            enqueue,
            rf"(?s)return\s+{re.escape(fresh_name)}.*?"
            r"guard\s+let\s+message\s*=\s*[A-Za-z_]\w*",
        )
        self.assertMatches(
            enqueue,
            r"(?s)if\s+message\.media\.contains.*?TelegramMediaExpiredContent.*?"
            r"media\s*=\s*marker\.media.*?else.*?media\s*=\s*message\.media",
        )
        self.assertOrdered(
            enqueue,
            "transaction.getMessage(message.id)",
            "TelegramMediaExpiredContent",
            "restoreConsumableMedia",
            "FileManager.default.temporaryDirectory",
        )
        self.assertNotContains(enqueue, "marker?.media ?? message.media")

    def test_safe_entity_fixture_uses_utf16_ranges_and_drops_custom_emoji(self) -> None:
        text = "A\U0001f600B"
        utf16_length = len(text.encode("utf-16-le")) // 2
        self.assertEqual(4, utf16_length)
        self.assertTrue(safe_entity(("Bold", 0, 1), utf16_length))
        self.assertTrue(safe_entity(("Italic", 1, 3), utf16_length))
        self.assertFalse(safe_entity(("CustomEmoji", 1, 3), utf16_length))
        self.assertFalse(safe_entity(("Bold", -1, 1), utf16_length))
        self.assertFalse(safe_entity(("Bold", 1, 1), utf16_length))
        self.assertFalse(safe_entity(("Bold", 3, 5), utf16_length))
        self.assertEqual(
            ("FileName", "ImageSize", "Sticker", "Animated", "Video", "Audio"),
            safe_file_attributes(
                (
                    "FileName",
                    "HasLinkedStickers",
                    "ImageSize",
                    "Sticker",
                    "hintFileIsLarge",
                    "Animated",
                    "NoPremium",
                    "Video",
                    "CustomEmoji",
                    "Audio",
                    "hintIsValidated",
                )
            ),
        )

    def test_local_copy_uses_fresh_positive_standalone_resources_and_safe_metadata(self) -> None:
        enqueue = source("submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift")
        attribute_switch = swift_block(enqueue, "switch attribute")
        entity_switch = swift_block(enqueue, "switch entity.type")
        custom_emoji_case = switch_case(entity_switch, "case .CustomEmoji:")
        self.assertContainsAll(
            enqueue,
            "enum GRVMPreservedMediaEnqueueError: Error",
            "case unsupported",
            "case unavailable",
            "Signal<GRVMPreservedMediaEnqueuePayload, GRVMPreservedMediaEnqueueError>",
            ".fail(.unsupported)",
            ".fail(.unavailable)",
            "restoreConsumableMedia",
            "completedResourcePath",
            "LocalFileReferenceMediaResource",
            "FileManager.default.temporaryDirectory",
            "linkItem",
            "copyItem",
            "isUniquelyReferencedTemporaryFile: true",
            "Namespaces.Media.LocalImage",
            "Namespaces.Media.LocalFile",
            ".standalone(media:",
            "partialReference: nil",
            "reference: nil",
            "immediateThumbnailData: nil",
            "TextEntitiesMessageAttribute",
            "inlineStickers: [:]",
            "switch attribute",
            "case .FileName",
            "case .ImageSize",
            "case .Sticker",
            "case .Animated",
            "case .Video",
            "case .Audio",
            "case .CustomEmoji",
            "(text as NSString).length",
            "entity.range.lowerBound >= 0",
            "entity.range.upperBound <= (text as NSString).length",
            "replyToMessageId: nil",
            "replyToStoryId: nil",
            "default:",
            "videoThumbnails: []",
            "videoCover: nil",
            "alternativeRepresentations: []",
        )
        self.assertMatches(enqueue, r"(?s)guard\s+.*(size|byteCount).*?>\s*0")
        enqueue_restore_calls = swift_calls(enqueue, "restoreConsumableMedia")
        self.assertGreaterEqual(len(enqueue_restore_calls), 1)
        for restore_call in enqueue_restore_calls:
            self.assertRegex(
                restore_call,
                r"(?s)(?:accountPeerId|context\.account\.peerId)\s*,\s*message\b",
            )
        self.assertRegex(
            enqueue,
            r"(?s)restoreConsumableMedia.*?\{\s*(?P<restored>[A-Za-z_]\w*)\s+in.*?"
            r"(?:guard\s+(?P=restored)\s+else|if\s+!(?P=restored)).*?\.fail\(\.unavailable\)",
        )
        resource_calls = swift_calls(enqueue, "LocalFileReferenceMediaResource")
        self.assertGreaterEqual(len(resource_calls), 1)
        resource_call = resource_calls[0]
        resource_bindings = set(re.findall(
            r"(?:let|var)\s+(?P<resource>[A-Za-z_]\w*)\s*=\s*LocalFileReferenceMediaResource\(",
            enqueue,
        ))
        self.assertTrue(resource_bindings)
        resource_temp = re.search(
            r"localFilePath\s*:\s*(?P<temp>[A-Za-z_]\w*)(?:\.path)?",
            resource_call,
        )
        resource_size = re.search(r"\bsize\s*:\s*(?P<size>[A-Za-z_]\w*)", resource_call)
        self.assertIsNotNone(resource_temp, msg="The local resource must own the unique temp path")
        self.assertIsNotNone(resource_size, msg="The local resource must own the verified positive size")
        temp_name = resource_temp.group("temp")
        size_name = resource_size.group("size")
        self.assertRegex(
            enqueue,
            rf"(?s)(?:let|var)\s+{re.escape(temp_name)}\s*=\s*"
            r"FileManager\.default\.temporaryDirectory.*?(?:UUID\(\)\.uuidString|Int64\.random)",
        )
        self.assertRegex(enqueue, rf"(?:guard|if)[^\n{{]*{re.escape(size_name)}\s*>\s*0")
        self.assertContains(resource_call, "isUniquelyReferencedTemporaryFile: true")

        link_calls = swift_calls(enqueue, "linkItem")
        copy_calls = swift_calls(enqueue, "copyItem")
        self.assertGreaterEqual(len(link_calls), 1)
        self.assertGreaterEqual(len(copy_calls), 1)
        link_arguments = re.search(
            r"at\s*:\s*(?P<source>[A-Za-z_]\w*)\s*,\s*to\s*:\s*(?P<temp>[A-Za-z_]\w*)",
            link_calls[0],
        )
        copy_arguments = re.search(
            r"at\s*:\s*(?P<source>[A-Za-z_]\w*)\s*,\s*to\s*:\s*(?P<temp>[A-Za-z_]\w*)",
            copy_calls[0],
        )
        self.assertIsNotNone(link_arguments)
        self.assertIsNotNone(copy_arguments)
        self.assertEqual(link_arguments.group("source"), copy_arguments.group("source"))
        self.assertEqual(temp_name, link_arguments.group("temp"))
        self.assertEqual(temp_name, copy_arguments.group("temp"))
        source_name = link_arguments.group("source")
        self.assertRegex(
            enqueue,
            rf"(?s)(?:let|guard\s+let)\s+{re.escape(source_name)}\s*=.*?completedResourcePath",
        )
        self.assertRegex(
            enqueue,
            rf"(?s)do\s*\{{[^}}]*linkItem\([^}}]*\}}\s*catch\s*\{{[^}}]*copyItem\(",
        )
        self.assertContains(attribute_switch, "default:")
        self.assertNotContains(attribute_switch, "attributes.append(attribute)")
        self.assertContains(entity_switch, "switch entity.type")
        self.assertContains(custom_emoji_case, "case .CustomEmoji:")
        self.assertAnyContains(custom_emoji_case, "continue", "return nil", "return false")
        for entity_kind in SAFE_ENTITIES:
            self.assertContains(entity_switch, f".{entity_kind}")
        self.assertContains(entity_switch, "default:")
        self.assertAnyContains(enqueue, "message.media.count", "media.count !=", "media.count <=")
        self.assertRegex(enqueue, r"(?s)\.message\(\s*text:\s*message\.text.*?mediaReference:\s*nil")
        self.assertRegex(
            enqueue,
            r"(?s)\.message\(\s*text:\s*message\.text.*?mediaReference:\s*\.standalone\(media:\s*"
            r"(?P<clone>[A-Za-z_]\w*)\)",
        )
        media_id_bindings = re.findall(
            r"(?:let|var)\s+(?P<id>[A-Za-z_]\w*)\s*=\s*Int64\.random",
            enqueue,
        )
        self.assertTrue(media_id_bindings, msg="Every cloned media path needs a fresh local ID")
        file_clone_calls = [
            call
            for call in swift_calls(enqueue, "TelegramMediaFile")
            if "Namespaces.Media.LocalFile" in call
        ]
        image_clone_calls = [
            call
            for call in swift_calls(enqueue, "TelegramMediaImage")
            if "Namespaces.Media.LocalImage" in call
        ]
        self.assertGreaterEqual(len(file_clone_calls), 1)
        self.assertGreaterEqual(len(image_clone_calls), 1)
        file_clone = file_clone_calls[0]
        image_clone = image_clone_calls[0]
        file_media_id = re.search(r"fileId:.*?\bid:\s*(?P<id>[A-Za-z_]\w*)", file_clone, re.DOTALL)
        image_media_id = re.search(r"imageId:.*?\bid:\s*(?P<id>[A-Za-z_]\w*)", image_clone, re.DOTALL)
        self.assertIsNotNone(file_media_id)
        self.assertIsNotNone(image_media_id)
        self.assertIn(file_media_id.group("id"), media_id_bindings)
        self.assertIn(image_media_id.group("id"), media_id_bindings)
        file_resource = re.search(r"\bresource:\s*(?P<resource>[A-Za-z_]\w*)", file_clone)
        image_resource = re.search(r"\bresource:\s*(?P<resource>[A-Za-z_]\w*)", image_clone)
        self.assertIsNotNone(file_resource)
        self.assertIsNotNone(image_resource)
        self.assertIn(file_resource.group("resource"), resource_bindings)
        self.assertIn(image_resource.group("resource"), resource_bindings)
        self.assertRegex(file_clone, r"mimeType:\s*[A-Za-z_]\w*\.mimeType")
        self.assertRegex(file_clone, rf"\bsize:\s*{re.escape(size_name)}\b")
        self.assertRegex(image_clone, r"dimensions:\s*[A-Za-z_]\w*\.dimensions")
        self.assertRegex(
            attribute_switch,
            r"(?s)case\s+let\s+\.FileName\((?P<fileName>[A-Za-z_]\w*)\).*?"
            r"append\(\.FileName\(fileName:\s*(?P=fileName)\)\)",
        )
        self.assertRegex(
            attribute_switch,
            r"(?s)case\s+let\s+\.Audio\([^)]*(?P<duration>[A-Za-z_]\w*)[^)]*\).*?"
            r"append\(\.Audio\([^)]*duration:\s*(?P=duration)",
        )
        self.assertRegex(
            attribute_switch,
            r"(?s)case\s+let\s+\.Video\((?P<duration>[A-Za-z_]\w*)\s*,\s*"
            r"(?P<dimensions>[A-Za-z_]\w*)[^)]*\).*?append\(\.Video\(duration:\s*(?P=duration),"
            r"\s*size:\s*(?P=dimensions)",
        )
        self.assertRegex(
            enqueue,
            r"(?s)var\s+(?P<messageAttributes>[A-Za-z_]\w*)\s*:\s*\[MessageAttribute\]\s*=\s*\[\]"
            r".*?(?P=messageAttributes)\.append\(TextEntitiesMessageAttribute",
        )
        enqueue_calls = [
            call
            for call in swift_calls(enqueue, ".message")
            if "mediaReference:" in call and "text:" in call
        ]
        self.assertGreaterEqual(len(enqueue_calls), 2)
        clone_bindings = set(
            re.findall(
                r"(?:let|var)\s+([A-Za-z_]\w*)\s*=\s*TelegramMedia(?:File|Image)\(",
                enqueue,
            )
        )
        for message_call in enqueue_calls:
            self.assertNotRegex(message_call, r"attributes\s*:\s*message\.attributes")
            self.assertTrue(
                message_attributes_are_allowlist_only(enqueue, message_call),
                msg=(
                    "The attributes variable passed to EnqueueMessage must be built from [] "
                    "and receive only safe TextEntitiesMessageAttribute values"
                ),
            )
            standalone = re.search(r"\.standalone\(media:\s*(?P<clone>[A-Za-z_]\w*)\)", message_call)
            if standalone is not None:
                self.assertIn(standalone.group("clone"), clone_bindings)
            for forbidden_attribute in (
                "AutoremoveTimeoutMessageAttribute",
                "AutoclearTimeoutMessageAttribute",
                "ConsumableContentMessageAttribute",
                "ReplyMarkupMessageAttribute",
                "ForwardSourceInfoAttribute",
                "SourceReferenceMessageAttribute",
                "ReplyMessageAttribute",
            ):
                self.assertNotContains(message_call, forbidden_attribute)

        self.assertTrue(
            local_copy_temp_cleanup_is_fail_closed(enqueue, temp_name),
            msg=(
                "Every temp-file failure/catch path must clean the exact temp path, while "
                "the successful standalone handoff retains it for stock move ownership"
            ),
        )
        for forbidden in (
            ".forward(",
            "enqueueMessages(",
            "pendingMessageManager",
            "network.request",
            "fetchedResource",
            "HasLinkedStickers",
            "hintFileIsLarge",
            "hintIsValidated",
            "NoPremium",
            "copyProtectionEnabled",
            "isCopyProtected",
            "noForwards",
        ):
            self.assertNotContains(enqueue, forbidden)
        self.assertNotRegex(enqueue, r"attributes\s*:\s*message\.attributes")

    def test_local_copy_bridge_is_nullable_chat_owned_and_separate_from_stock_forward(self) -> None:
        interaction = source(
            "submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift"
        )
        chat_controller = source("submodules/TelegramUI/Sources/ChatController.swift")
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        local_forward = swift_block(forward, "func forwardLocalCopy(message: Message)")
        common_forward = swift_block(forward, "func forwardMessages(messages: [Message]")
        eligibility = swift_block(context_menu, "func grvmCanForwardLocalCopy(")
        local_item, local_action = action_item_containing(
            context_menu, "grvmForwardLocalCopy?(message)"
        )
        self.assertContainsAll(
            eligibility,
            "messages.count == 1",
            "isLocallyDeletedMessage",
            "minAutoremoveOrClearTimeout",
            "copyProtectionEnabled",
            "isCopyProtected()",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "completedResourcePath",
            "restoreConsumableMedia",
            "accountPeerId",
        )
        self.assertAnyContains(eligibility, "!message.text.isEmpty", "message.text.isEmpty == false")
        self.assertAnyContains(
            eligibility,
            "message.media.count",
            "message.media.isEmpty",
            "media.count",
            "media.isEmpty",
        )
        self.assertMatches(
            eligibility,
            r"(?s)completedResourcePath.*?(?:fileSize|byteCount|size).*?>\s*0",
        )
        restore_calls = swift_calls(eligibility, "restoreConsumableMedia")
        self.assertEqual(1, len(restore_calls))
        self.assertRegex(restore_calls[0], r"(?s)accountPeerId\s*,\s*message\b")
        self.assertTrue(
            any(
                "context.account.peerId" in call
                for call in swift_calls(context_menu, "grvmCanForwardLocalCopy")
            ),
            msg="Local-copy eligibility must receive the exact account peer ID",
        )
        self.assertContains(eligibility, ".single(false)")
        self.assertRegex(
            eligibility,
            r"(?s)restoreConsumableMedia.*?\|>\s*(?:map|mapToSignal)\s*\{\s*"
            r"(?P<restored>[A-Za-z_]\w*)\s+in.*?return\s+(?P=restored)",
        )
        self.assertContains(interaction, "public var grvmForwardLocalCopy: ((Message) -> Void)?")
        self.assertContains(chat_controller, "controllerInteraction.grvmForwardLocalCopy = { [weak self] message in")
        self.assertTrue(local_item)
        self.assertContainsAll(
            local_action,
            "grvmForwardLocalCopy?(message)",
        )
        local_gate = None
        for match in re.finditer(r"if\s+(?P<flag>[A-Za-z_]\w*)\s*\{", context_menu):
            block, _ = swift_block_at(context_menu, match.start())
            if local_item in block:
                local_gate = match
                break
        self.assertIsNotNone(local_gate)
        local_flag = local_gate.group("flag")
        local_prefix = context_menu[max(0, local_gate.start() - 9000) : local_gate.start()]
        self.assertContains(local_prefix, "grvmCanForwardLocalCopy(")
        self.assertRegex(
            local_prefix,
            rf"(?s)\|>\s*(?:map|mapToSignal)\s*\{{[^\n{{}}]*\b{re.escape(local_flag)}\b[^\n{{}}]*\bin\b",
        )
        self.assertContainsAll(
            local_forward,
            "func forwardLocalCopy(message: Message)",
            "GRVMPreservedMediaEnqueue",
            "localCopy: Signal<GRVMPreservedMediaEnqueuePayload",
            "forwardMessages(messages:",
        )
        self.assertContains(local_forward, "localCopy: localCopy")
        self.assertNotContains(local_forward, ".start")
        self.assertNotContains(local_forward, ".forward(source:")
        self.assertNotContains(local_forward, "withUpdatedForwardMessageIds")
        self.assertOrdered(local_forward, "GRVMPreservedMediaEnqueue", "forwardMessages(messages:")
        error_switch = swift_block(common_forward, "switch error")
        for error_case in ("case .unsupported", "case .unavailable"):
            error_branch = switch_case(error_switch, error_case)
            self.assertContains(error_branch, "displayUndo")
            self.assertNotContains(error_branch, "chatMessagePaymentAlertController")
            self.assertNotContains(error_branch, "enqueueMessages(")

    def test_local_copy_temp_lifetime_is_owned_until_stock_enqueue(self) -> None:
        enqueue = source("submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift")
        payload = swift_block(enqueue, "final class GRVMPreservedMediaEnqueuePayload")
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        common_forward = swift_block(forward, "func forwardMessages(messages: [Message]")
        commit = swift_block(common_forward, "let commit: ([EnqueueMessage]) -> Void")
        self.assertContainsAll(
            payload,
            "let message: EnqueueMessage",
            "temporaryFile",
            "func transferOwnership()",
            "deinit",
            "removeItem",
        )
        self.assertContainsAll(
            common_forward,
            "localCopy: Signal<GRVMPreservedMediaEnqueuePayload",
            "preparedLocalCopy",
            "chatMessagePaymentAlertController",
        )
        preparation = swift_block(common_forward, "if let localCopy")
        self.assertContains(preparation, "preparedLocalCopy")
        self.assertContainsAll(
            commit,
            "preparedLocalCopy?.transferOwnership()",
            "enqueueMessages(",
        )
        self.assertLess(
            common_forward.find("if let localCopy"),
            common_forward.find("chatMessagePaymentAlertController"),
        )
        self.assertOrdered(commit, "transferOwnership()", "enqueueMessages(")

    def test_local_copy_single_selection_preserves_forum_thread(self) -> None:
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        common_forward = swift_block(forward, "func forwardMessages(messages: [Message]")
        peer_selected = swift_block(common_forward, "controller.peerSelected =")
        self.assertNotContains(
            common_forward,
            "immediatelyActivateMultipleSelection: localCopy != nil",
        )
        self.assertContainsAll(
            peer_selected,
            "if localCopy != nil",
            "threadId",
            "multiplePeersSelected?",
            "return",
        )
        self.assertContainsAll(
            common_forward,
            "localCopyThreadIds",
            "withUpdatedThreadId",
        )
        local_branch = swift_block(peer_selected, "if localCopy != nil")
        self.assertOrdered(
            local_branch,
            "if localCopy != nil",
            "threadId",
            "multiplePeersSelected?",
            "return",
        )

    def test_local_copy_reuses_stock_selector_paid_commit_enqueue_and_pending_pipeline(self) -> None:
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        common_forward = swift_block(forward, "func forwardMessages(messages: [Message]")
        self.assertContainsAll(
            common_forward,
            ".onlyWriteable",
            ".excludeDisabled",
            "selectForumThreads: true",
            "switch mode",
            "case .generic:",
            "case .silent:",
            "case .schedule:",
            "case .whenOnline:",
            "chatMessagePaymentAlertController",
            "OutgoingScheduleInfoMessageAttribute",
            "PaidStarsMessageAttribute",
            "shouldDivertMessagesToScheduled",
            "enqueueMessages(",
            "pendingMessageStatus",
            "if let localCopy",
            "preparedLocalCopy",
            "transferOwnership()",
            "commit(",
        )
        self.assertMatches(
            common_forward,
            r"forwardedMessageIds:\s*(?:"
            r"localCopy\s*==\s*nil\s*\?\s*messages\.map\s*\{\s*\$0\.id\s*\}\s*:\s*nil|"
            r"localCopy\s*!=\s*nil\s*\?\s*nil\s*:\s*messages\.map\s*\{\s*\$0\.id\s*\})",
        )
        self.assertOrdered(common_forward, "if let localCopy", "chatMessagePaymentAlertController")
        self.assertMatches(
            common_forward,
            r"(?s)if let preparedLocalCopy.*result.*preparedLocalCopy\.message.*commit\(",
        )
        self.assertEqual(1, common_forward.count("let commit: ([EnqueueMessage]) -> Void"))

    def test_stock_forward_remains_server_referenced_and_keeps_both_routes(self) -> None:
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        common_forward = swift_block(forward, "func forwardMessages(messages: [Message]")
        local_forward = swift_block(forward, "func forwardLocalCopy(message: Message)")
        stock_forward_calls = [
            call
            for call in swift_calls(common_forward, ".forward")
            if "source: message.id" in call
        ]
        self.assertGreaterEqual(len(stock_forward_calls), 2)
        self.assertTrue(any("threadId: nil" in call for call in stock_forward_calls))
        self.assertTrue(any("threadId: nil" not in call for call in stock_forward_calls))
        self.assertRegex(
            common_forward,
            r"forwardedMessageIds:\s*(?:messages\.map\s*\{\s*\$0\.id\s*\}|"
            r"localCopy\s*==\s*nil\s*\?\s*messages\.map\s*\{\s*\$0\.id\s*\})",
        )
        self.assertNotContains(local_forward, ".forward(source:")


if __name__ == "__main__":
    unittest.main()
