import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT.parent / "GRVM-Notify"
WEB_CHECKOUT_EXISTS = (WEB_ROOT / ".git").exists()
SHARED_URL_TOKENS = (
    "grvmgram",
    "notify-auth",
    "notify-open",
    "account_user_id",
    "peer_type",
    "peer_id",
    "message_id",
)
DEVICE_CASES = (
    "GN01 — Add to Home Screen and click count",
    "GN02 — Permission denied/recovery",
    "GN03 — Same-device auth and session in Devices",
    "GN04 — Single-account block under login churn",
    "GN05 — Passcode OFF closed plain preview",
    "GN06 — Passcode ON closed generic fallback",
    "GN07 — Live unlocked decrypt",
    "GN08 — Foreground/background/killed-IPA click",
    "GN09 — Exact user/group/channel/message and forum fallback",
    "GN10 — Missing peer/malformed payload safety",
    "GN11 — Register/unregister network retry",
    "GN12 — PWA/native/Devices revoke",
    "GN13 — Removed native account/orphaned ownership",
    "GN14 — Relaunch/account switch/seven-day Sideloadly re-sign",
)
NATIVE_REGRESSION_CARDS = (
    "GN-N01 — grvmgram cold/foreground routing",
    "GN-N02 — Locked readiness",
    "GN-N03 — Settings row/localization",
    "GN-N04 — Exact account/message navigation",
    "GN-N05 — Session revoke/orphaned state",
)
EXISTING_THIRD_BUILD_CARDS = (
    "ST15 — Прочитать сообщение",
    "ST20 — Сжечь",
    "ST21 — Повтор one-view/one-play",
    "ST22 — Переслать локальную копию",
    "Q05 — Стабильность mixed run",
    "Q01 — Единые настройки клиента",
    "G09 — Удалённая отложка / штатное Schedule Messages",
    "A06 — Удалённое отключение кастомных фонов / штатные обои",
    "C15 — Удалённые простые replies / штатный reply renderer",
    "A08 — Закругление аватаров",
    "C05 — Количество недавних стикеров",
    "Q04 — Layout",
    "A13 — Скрыть счётчики папок",
    "A14 — Скрыть «Все чаты»",
    "Q02 — Сохранение после relaunch",
    "C02 — Реакции в каналах",
    "C03 — Реакции в группах",
    "C04 — Реакции в private chats (regression guard)",
    "CM01 — Панель реакций",
    "AR05A — Безвозвратное удаление отдельной сохранённой удалёнки",
    "F22 — Shadow Ban forwarded origin",
    "SP04A — Поддерживаемое Local Premium compatibility state",
    "Q03 — EN/RU и branding",
)
WEB_PRODUCTION_SOURCE_PATHS = (
    "src/lib/grvmNotify/mode.ts",
    "src/lib/grvmNotify/authLink.ts",
    "src/lib/grvmNotify/setupState.ts",
    "src/lib/grvmNotify/pushPolicy.ts",
    "src/lib/grvmNotify/notificationTarget.ts",
    "src/components/grvmNotify/GRVMNotifySetup.tsx",
    "src/components/grvmNotify/GRVMNotifyLanding.tsx",
    "src/pages/bootstrapIm.ts",
    "src/pages/cards/SignQRCard.tsx",
    "src/lib/uiNotificationsManager.ts",
    "src/lib/appManagers/pushSingleManager.ts",
    "src/lib/webPushApiManager.ts",
    "src/lib/serviceWorker/push.ts",
)


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def combined_sources(paths: list[Path]) -> str:
    return "\n".join(
        f"// {path.as_posix()}\n{source(path)}"
        for path in sorted(set(paths))
        if path.is_file()
    )


def native_sources() -> str:
    source_roots = (
        ROOT / "submodules/AyuGramLib/Sources",
        ROOT / "submodules/TelegramUI/Sources",
        ROOT / "submodules/TelegramCore/Sources/TelegramEngine/Privacy",
    )
    paths: list[Path] = []
    for source_root in source_roots:
        if source_root.is_dir():
            paths.extend(source_root.rglob("GRVMNotify*.swift"))
    paths.append(ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift")
    return combined_sources(paths)


def web_sources() -> str:
    return combined_sources(
        [WEB_ROOT / relative_path for relative_path in WEB_PRODUCTION_SOURCE_PATHS]
    )


def markdown_cards(text: str) -> list[tuple[str, str]]:
    headings = list(re.finditer(r"(?m)^(#{1,3}) (.+)$", text))
    cards: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        if heading.group(1) != "###":
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        cards.append((heading.group(2), text[heading.end() : end]))
    return cards


class GRVMNotifyReleaseContractTests(unittest.TestCase):
    def assert_blank_result_fields(self, body: str) -> None:
        nonempty_lines = [line.rstrip() for line in body.splitlines() if line.strip()]
        self.assertGreaterEqual(len(nonempty_lines), 2)
        self.assertEqual(nonempty_lines[-2:], ["- **Статус:**", "- **Наблюдение:**"])
        self.assertEqual(body.count("- **Статус:**"), 1)
        self.assertEqual(body.count("- **Наблюдение:**"), 1)

    def test_native_sources_share_exact_url_schema(self) -> None:
        sources = native_sources()
        for token in SHARED_URL_TOKENS:
            with self.subTest(token=token):
                self.assertTrue(
                    token in sources,
                    msg=f"Native GRVM Notify sources are missing shared URL token: {token}",
                )
        self.assertTrue(
            "AccountRecordId(rawValue: accountUserId)" not in sources,
            msg="Native GRVM Notify must resolve a public user ID, not cast it to AccountRecordId",
        )

    @unittest.skipUnless(
        WEB_CHECKOUT_EXISTS,
        f"GRVM Notify Web sibling checkout is absent at {WEB_ROOT}; "
        "native-only CI skips Web source assertions",
    )
    def test_web_sources_share_exact_url_schema_and_safe_push_contract(self) -> None:
        sources = web_sources()
        self.assertTrue(sources, msg=f"No production TypeScript found under {WEB_ROOT / 'src'}")
        for token in SHARED_URL_TOKENS:
            with self.subTest(token=token):
                self.assertTrue(
                    token in sources,
                    msg=f"Web GRVM Notify sources are missing shared URL token: {token}",
                )
        for unsafe_getter in (
            "getCached('push_keys_ids_base64')",
            'getCached("push_keys_ids_base64")',
        ):
            with self.subTest(unsafe_getter=unsafe_getter):
                self.assertTrue(
                    unsafe_getter not in sources,
                    msg="Cold Service Worker push-key loading must not use the cached-only getter",
                )
        self.assertTrue(
            "other_uids: userIds" in sources,
            msg="Web registration must send other_uids as the userIds array",
        )

    def test_native_build_workflow_keeps_manual_validated_ipa_and_failure_log(self) -> None:
        workflow = source(ROOT / ".github/workflows/build.yml")
        self.assertRegex(workflow, r"(?m)^\s{2}workflow_dispatch:\s*$")
        self.assertRegex(workflow, r"(?m)^\s+name:\s*GRVMgram-ipa\s*$")
        self.assertRegex(workflow, r"ValidateGRVMgram\.py\s+ipa(?:\s|$)")

        marker = "- name: Upload build log"
        self.assertIn(marker, workflow)
        build_log_step = workflow[workflow.index(marker) :]
        self.assertRegex(build_log_step, r"(?m)^\s+if:\s*(?:always|failure)\(\)\s*$")
        self.assertIn("uses: actions/upload-artifact@", build_log_step)
        self.assertRegex(build_log_step, r"(?m)^\s+name:\s*build-log\s*$")

    def test_native_workflows_do_not_request_web_deployment_secrets(self) -> None:
        workflow_root = ROOT / ".github/workflows"
        workflows = combined_sources(
            [*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")]
        )
        self.assertIsNone(
            re.search(
                r"\b(?:CLOUDFLARE|CF_API_TOKEN|CF_ACCOUNT_ID|WRANGLER)\b",
                workflows,
                re.IGNORECASE,
            )
        )

    def test_device_journal_has_exactly_fourteen_blank_cases(self) -> None:
        journal = source(ROOT / "docs/grvm-notify-device-qa.md")
        cards = markdown_cards(journal)
        self.assertEqual([heading for heading, _ in cards], list(DEVICE_CASES))
        for heading, body in cards:
            with self.subTest(heading=heading):
                self.assert_blank_result_fields(body)

    def test_third_build_checklist_has_only_five_notify_regression_cards(self) -> None:
        checklist = source(ROOT / "docs/grvmgram-third-build-qa-checklist.md")
        cards = markdown_cards(checklist)
        headings = [heading for heading, _ in cards]
        self.assertEqual(len(headings), 28)
        self.assertEqual(len(set(headings)), 28)
        self.assertEqual(
            [heading for heading in headings if not heading.startswith("GN-N")],
            list(EXISTING_THIRD_BUILD_CARDS),
        )
        notify_cards = [(heading, body) for heading, body in cards if heading.startswith("GN-N")]
        self.assertEqual(
            [heading for heading, _ in notify_cards],
            list(NATIVE_REGRESSION_CARDS),
        )
        for heading, body in notify_cards:
            with self.subTest(heading=heading):
                self.assert_blank_result_fields(body)

    def test_ui_testing_documents_focused_contracts_without_claiming_device_pass(self) -> None:
        ui_testing = source(ROOT / "docs/ui-testing.md")
        for token in (
            "Tests.GRVMgramContracts.test_grvm_notify_native_contract",
            "Tests.GRVMgramContracts.test_grvm_notify_release_contract",
            "grvm-notify-device-qa.md",
            "iOS/iPadOS 16.4",
            "не являются device PASS",
        ):
            with self.subTest(token=token):
                self.assertIn(token, ui_testing)


if __name__ == "__main__":
    unittest.main()
