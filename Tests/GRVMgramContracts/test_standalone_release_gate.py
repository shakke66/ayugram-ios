import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STANDALONE_BASE = "fbea0a8f"
PLAN = ROOT / "docs/superpowers/plans/2026-07-15-grvmgram-standalone-features.md"


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def added_production_lines() -> str:
    diff = git_output(
        "diff",
        "--unified=0",
        f"{STANDALONE_BASE}..HEAD",
        "--",
        "submodules",
        "Telegram",
    )
    return "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def changed_production_paths() -> list[Path]:
    paths = git_output(
        "diff",
        "--name-only",
        f"{STANDALONE_BASE}..HEAD",
        "--",
        "submodules",
        "Telegram",
    ).splitlines()
    return [ROOT / path for path in paths if (ROOT / path).is_file()]


class StandaloneReleaseGateTests(unittest.TestCase):
    def test_added_production_has_no_forbidden_upstream_or_support_sources(self) -> None:
        added = added_production_lines()
        forbidden = {
            "AyuGram resolver bot": r"ayugrambot|resolvePeerByName",
            "Extera source": r"\bextera\b",
            "paste service": r"\bdpaste\b",
            "support or donation UI": (
                r"\bboosty\b|\bsupporter\b|support the developers|"
                r"\bdonation\b|\bcrypto\b"
            ),
            "custom official advertising": r"\bOfficial app\b",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, added, re.IGNORECASE))

    def test_stock_credibility_and_official_session_flags_remain_authoritative(self) -> None:
        bubble = source(
            "submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/"
            "Sources/ChatMessageBubbleItemNode.swift"
        )
        for token in ("effectiveAuthor.isScam", "effectiveAuthor.isFake", "effectiveAuthor.isVerified"):
            self.assertIn(token, bubble)

        sessions = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Privacy/RecentAccountSession.swift"
        )
        self.assertIn("accountSessionFlags.insert(.isOfficial)", sessions)
        self.assertIsNone(
            re.search(
                r"GRVM[A-Za-z0-9_]*(?:Official|Verified|Trusted)(?:Registry|Peer|Badge)",
                added_production_lines(),
                re.IGNORECASE,
            )
        )

    def test_local_data_privacy_and_media_boundaries_remain_present(self) -> None:
        contacts = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Contacts/TelegramEngineContacts.swift"
        )
        local_peers = contacts[contacts.index("public func localPeers(ids:") :]
        local_peers = local_peers[: local_peers.index("\n    }") + 6]
        self.assertIn("self.account.postbox.transaction", local_peers)
        self.assertNotRegex(local_peers, r"network|request\(|resolvePeerByName")

        profile = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/"
            "Sources/PeerInfoProfileItems.swift"
        )
        for token in ("cachedData.invitedOn", "channel.creationDate", "group.creationDate"):
            self.assertIn(token, profile)

        saved_music = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/"
            "Sources/GRVMSavedMusicColor.swift"
        )
        self.assertIn("mediaBox.resourceData(resource, attemptSynchronously: true)", saved_music)
        self.assertNotRegex(saved_music.lower(), r"urlsession|itunes|interactivefetched|fetchedmediaresource")

        streamer = source("submodules/TelegramUI/Sources/GRVMScreenCapturePrivacyController.swift")
        self.assertIn("UIScreen.capturedDidChangeNotification", streamer)
        self.assertIn("window.screen.isCaptured", streamer)

        gallery = source("submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift")
        self.assertIn(
            "if forceEnablePiP || (!isAnimated && !disablePlayerControls && !disablePictureInPicture)",
            gallery,
        )
        self.assertNotIn("if isAnimated || disablePlayerControls", gallery)

    def test_stock_notification_and_local_crash_export_boundaries_remain_present(self) -> None:
        item = source("submodules/TelegramUI/Sources/NotificationItemContainerNode.swift")
        container = source("submodules/TelegramUI/Sources/NotificationContainerControllerNode.swift")
        for token in (
            "contentInsets.top = statusBarHeight + 6.0",
            "contentInsets.top += 34.0",
            "y: -self.backgroundView.frame.maxY",
        ):
            self.assertIn(token, item)
        self.assertIn("containerNode.animateIn()", container)
        self.assertIn("topItemNode.animateOut", container)

        export = source("submodules/TelegramUI/Sources/GRVMLocalCrashExport.swift")
        app = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        self.assertIn("public init(rootPath: String)", export)
        self.assertIn("GRVMLocalCrashExport(rootPath: rootPath)", app)
        self.assertNotRegex(app, r"AppCenter\.start|Crashes\.start|MSACCrashes\.start")
        self.assertNotRegex(export.lower(), r"urlsession|network\.request|upload")

    def test_read_modes_and_preserved_media_have_exact_safe_routes(self) -> None:
        read_actions = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/GRVMReadActions.swift"
        )
        self.assertIn("case .localOnly", read_actions)
        self.assertIn("confirmSynchronizedIncomingReadState", read_actions)
        self.assertIn("case .forceServer", read_actions)
        self.assertIn("forceSynchronizeIncomingReadState", read_actions)

        bypass = source("submodules/TelegramCore/Sources/GRVMReadReceiptBypass.swift")
        for token in ("accountPeerId", "peerId", "maxIncomingReadId", "expiresAt"):
            self.assertIn(token, bypass)

        required = {
            "submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift": (
                "GRVMPreservedConsumableMediaAttribute",
                "resourceIds",
                "preparedAt",
            ),
            "submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift": (
                "LocalFileReferenceMediaResource",
                ".standalone",
                "case unavailable",
            ),
            "submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift": (
                "force: Bool",
                '"f"',
            ),
            "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift": (
                "prepareConsumableMedia",
                "restoreArchivedMedia",
            ),
        }
        for path, tokens in required.items():
            text = source(path)
            with self.subTest(path=path):
                self.assertTrue(text, msg=f"Missing Task 10 production file: {path}")
                for token in tokens:
                    self.assertIn(token, text)

        menu = source("submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift")
        for token in ("force: true", "consumeOnOpen: false", "grvmForwardLocalCopy"):
            self.assertIn(token, menu)

    def test_plan_stages_exact_files_and_new_settings_have_consumers(self) -> None:
        plan = PLAN.read_text(encoding="utf-8")
        broad_add = re.compile(
            r"(?m)^\s*git add\s+submodules/(?:TelegramCore|TelegramUI|AyuGramFeatures)(?:\s|$)"
        )
        self.assertIsNone(broad_add.search(plan))

        settings_diff = git_output(
            "diff",
            "--unified=0",
            f"{STANDALONE_BASE}..HEAD",
            "--",
            "submodules/AyuGramLib/Sources/AyuGramSettings.swift",
        )
        added_fields = set(re.findall(r"^\+\s*public var ([A-Za-z_]\w*)\s*:", settings_diff, re.MULTILINE))
        consumers = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in changed_production_paths()
            if path.name != "AyuGramSettings.swift"
        )
        for field in sorted(added_fields):
            with self.subTest(field=field):
                self.assertIn(field, consumers, msg=f"Standalone setting has no implementation consumer: {field}")


if __name__ == "__main__":
    unittest.main()
