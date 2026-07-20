from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SWIFT = ROOT / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
ENGLISH = ROOT / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
RUSSIAN = ROOT / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"

EXPECTED_KEYS = frozenset(
    """
GRVMgram.Brand.Name
GRVMgram.Settings.Title
GRVMgram.Main.Core
GRVMgram.Main.Filters
GRVMgram.Main.General
GRVMgram.Main.Appearance
GRVMgram.Main.Chats
GRVMgram.Main.Other
GRVMgram.Main.Deleted
GRVMgram.Main.History
GRVMgram.Common.Default
GRVMgram.Common.Off
GRVMgram.Common.Hidden
GRVMgram.Common.Shown
GRVMgram.Common.WithModifier
GRVMgram.Common.Never
GRVMgram.Common.InGhost
GRVMgram.Common.Always
GRVMgram.Common.Search
GRVMgram.Common.Clear
GRVMgram.Common.Export
GRVMgram.Common.Import
GRVMgram.Core.Title
GRVMgram.Ghost.Header
GRVMgram.Ghost.Master
GRVMgram.Ghost.ReadReceipts
GRVMgram.Ghost.StoryViews
GRVMgram.Ghost.Online
GRVMgram.Ghost.Typing
GRVMgram.Ghost.Upload
GRVMgram.Ghost.AutoOffline
GRVMgram.Ghost.LockedComponents
GRVMgram.Ghost.LockedCount
GRVMgram.Ghost.Component.ReadReceipts
GRVMgram.Ghost.Component.StoryViews
GRVMgram.Ghost.Component.OnlineStatus
GRVMgram.Ghost.Component.TypingUploads
GRVMgram.Ghost.Component.AutoOffline
GRVMgram.Ghost.ReadOnAction
GRVMgram.Ghost.ReadOnAction.Info
GRVMgram.Ghost.StoryPrompt
GRVMgram.Ghost.StoryPrompt.Info
GRVMgram.Ghost.Schedule
GRVMgram.Ghost.Schedule.Info
GRVMgram.Ghost.Silent
GRVMgram.Ghost.Silent.Info
GRVMgram.Ghost.ActiveCount
GRVMgram.Spy.Header
GRVMgram.Spy.SaveDeleted
GRVMgram.Spy.SaveEdits
GRVMgram.Spy.SaveBots
GRVMgram.Core.Other.Header
GRVMgram.Core.LocalPremium
GRVMgram.Core.DisableAds
GRVMgram.Filters.Title
GRVMgram.Filters.Header
GRVMgram.Filters.Enable
GRVMgram.Filters.InChats
GRVMgram.Filters.Blocked
GRVMgram.Filters.Patterns
GRVMgram.Filters.Add
GRVMgram.Filters.AddPrompt
GRVMgram.Filters.EditPrompt
GRVMgram.Filters.Reversed
GRVMgram.Filters.AddReversed
GRVMgram.Filters.AddReversedPrompt
GRVMgram.Filters.EditReversedPrompt
GRVMgram.Filters.Global
GRVMgram.Filters.CaseSensitive
GRVMgram.Filters.Type
GRVMgram.Filters.Button
GRVMgram.Filters.SelectChat
GRVMgram.Filters.ShowFiltered
GRVMgram.Filters.HideFiltered
GRVMgram.Filters.Clear
GRVMgram.Filters.State.Normal
GRVMgram.Filters.State.Reversed
GRVMgram.Filters.CaseInsensitive
GRVMgram.Filters.Scope.AllChats
GRVMgram.Filters.Scope.Chat
GRVMgram.Filters.ExcludedCount
GRVMgram.Filters.Empty
GRVMgram.Filters.Backup.Header
GRVMgram.Filters.Import.Title
GRVMgram.Filters.Import.Summary
GRVMgram.Filters.Import.Replace
GRVMgram.Filters.InvalidFile.Title
GRVMgram.Filters.InvalidFile.Text
GRVMgram.Filters.Clear.Title
GRVMgram.Filters.Clear.Text
GRVMgram.Filters.Matching.Title
GRVMgram.Filters.People
GRVMgram.FilterEditor.AddTitle
GRVMgram.FilterEditor.EditTitle
GRVMgram.FilterEditor.Expression.Header
GRVMgram.FilterEditor.Expression.Placeholder
GRVMgram.FilterEditor.Options.Header
GRVMgram.FilterEditor.Enabled
GRVMgram.FilterEditor.Reversed
GRVMgram.FilterEditor.CaseInsensitive
GRVMgram.FilterEditor.Scope.Header
GRVMgram.FilterEditor.Scope.Chat
GRVMgram.FilterEditor.Scope.AllChats
GRVMgram.FilterEditor.Scope.UseAllChats
GRVMgram.FilterEditor.ExcludedChats
GRVMgram.FilterEditor.None
GRVMgram.FilterEditor.ClearExcluded
GRVMgram.FilterEditor.SelectChat
GRVMgram.FilterEditor.ExcludeChats
GRVMgram.FilterEditor.Invalid.Title
GRVMgram.FilterEditor.Invalid.Text
GRVMgram.Shadow.Title
GRVMgram.Shadow.IDs
GRVMgram.Shadow.Add
GRVMgram.Shadow.AddPrompt
GRVMgram.Shadow.EditPrompt
GRVMgram.Shadow.Empty
GRVMgram.Shadow.Unban
GRVMgram.Shadow.Author
GRVMgram.Shadow.ForwardedAuthor
GRVMgram.Shadow.ActionWithRole
GRVMgram.General.Title
GRVMgram.Translation.Header
GRVMgram.Translation.Provider
GRVMgram.Translation.Telegram
GRVMgram.Translation.Google
GRVMgram.Translation.Yandex
GRVMgram.Translation.Privacy
GRVMgram.General.Header
GRVMgram.General.HideStories
GRVMgram.General.SimilarChannels
GRVMgram.General.NotificationDelay
GRVMgram.General.Seconds
GRVMgram.General.PeerID
GRVMgram.General.Zalgo
GRVMgram.General.LinkPreviews
GRVMgram.General.LinkWarning
GRVMgram.General.PeerID.API
GRVMgram.General.PeerID.BotAPI
GRVMgram.Webview.Header
GRVMgram.Webview.Android
GRVMgram.Webview.Height
GRVMgram.Webview.Width
GRVMgram.Confirmations.Header
GRVMgram.Confirmations.Sticker
GRVMgram.Confirmations.GIF
GRVMgram.Confirmations.Voice
GRVMgram.Appearance.Title
GRVMgram.AppIcon.Header
GRVMgram.AppIcon.Title
GRVMgram.AppIcon.Default
GRVMgram.AppIcon.Black
GRVMgram.AppIcon.BlackClassic
GRVMgram.AppIcon.BlackFilled
GRVMgram.AppIcon.Blue
GRVMgram.AppIcon.BlueClassic
GRVMgram.AppIcon.BlueFilled
GRVMgram.AppIcon.WhiteFilled
GRVMgram.AppIcon.New1
GRVMgram.AppIcon.New2
GRVMgram.AppIcon.Premium
GRVMgram.AppIcon.PremiumBlack
GRVMgram.AppIcon.PremiumTurbo
GRVMgram.Appearance.HideBadge
GRVMgram.Appearance.HideCounters
GRVMgram.Appearance.Header
GRVMgram.Appearance.MD3
GRVMgram.Appearance.Tail
GRVMgram.Appearance.Backgrounds
GRVMgram.Appearance.CodeFont
GRVMgram.Appearance.AvatarCorners
GRVMgram.Appearance.BubbleRadius
GRVMgram.Appearance.SingleCorner
GRVMgram.Appearance.PremiumStatuses
GRVMgram.Appearance.AdaptiveSavedMusicColor
GRVMgram.Appearance.Folders
GRVMgram.Appearance.FolderCounters
GRVMgram.Appearance.AllChats
GRVMgram.Chats.Title
GRVMgram.Chats.Stickers.Header
GRVMgram.Chats.Stickers.OnlyAdded
GRVMgram.Chats.Stickers.ChannelReactions
GRVMgram.Chats.Stickers.GroupReactions
GRVMgram.Chats.Stickers.PrivateReactions
GRVMgram.Chats.Stickers.Recent
GRVMgram.Chats.Channels.Header
GRVMgram.Chats.Channels.QuickAdmin
GRVMgram.Chats.Channels.MessageShot
GRVMgram.Chats.Channels.BottomButton
GRVMgram.Chats.Channels.BottomButton.Hide
GRVMgram.Chats.Channels.BottomButton.Mute
GRVMgram.Chats.Channels.BottomButton.Discuss
GRVMgram.Chats.Messages.Header
GRVMgram.Chat.DeletedMark
GRVMgram.Chat.DeletedMark.Visible
GRVMgram.Chat.DeletedMark.Prompt
GRVMgram.Chat.DeletedMark.Default
GRVMgram.Chat.EditedMark
GRVMgram.Chat.EditedMark.Visible
GRVMgram.Chat.EditedMark.Prompt
GRVMgram.Chat.EditedMark.Default
GRVMgram.Chats.Messages.Icons
GRVMgram.Chats.Messages.FastShare
GRVMgram.Chats.Messages.ColoredReplies
GRVMgram.Chats.Messages.Width
GRVMgram.Chats.Messages.Translucent
GRVMgram.Chats.Context.Header
GRVMgram.Chats.Context.Reactions
GRVMgram.Chats.Context.Views
GRVMgram.Chats.Context.Hide
GRVMgram.Chats.Context.UserMessages
GRVMgram.Chats.Context.Details
GRVMgram.Chats.Context.Repeat
GRVMgram.Chats.Context.AddFilter
GRVMgram.Chats.Context.MoreActions
GRVMgram.Chats.Field.Header
GRVMgram.Chats.Field.Attach
GRVMgram.Chats.Field.AttachPopup
GRVMgram.Chats.Field.Commands
GRVMgram.Chats.Field.TTL
GRVMgram.Chats.Field.Emoji
GRVMgram.Chats.Field.EmojiPopup
GRVMgram.Chats.Field.Voice
GRVMgram.Chats.Field.Gift
GRVMgram.Chats.Field.AI
GRVMgram.Deleted.Title
GRVMgram.Deleted.Empty
GRVMgram.Deleted.Recent
GRVMgram.Deleted.MessageEmpty
GRVMgram.Deleted.Media
GRVMgram.Deleted.MediaWithText
GRVMgram.Deleted.Author
GRVMgram.Deleted.Attachment
GRVMgram.Deleted.MediaUnavailable
GRVMgram.Deleted.ArchivedResources
GRVMgram.Deleted.Clear.Title
GRVMgram.Deleted.Clear.Text
GRVMgram.Deleted.Clear.Action
GRVMgram.Deleted.Clear.ErrorTitle
GRVMgram.Deleted.Clear.ArchiveUnavailable
GRVMgram.Deleted.Clear.MediaRemovalFailed
GRVMgram.Deleted.Clear.DatabaseFinalizationFailed
GRVMgram.History.Title
GRVMgram.History.Info
GRVMgram.History.Empty
GRVMgram.History.Recent
GRVMgram.History.Current
GRVMgram.History.Revision
GRVMgram.History.Action
GRVMgram.History.EntryHeader
GRVMgram.History.ArchivedResources
GRVMgram.History.Media.Todo
GRVMgram.History.Media.Poll
GRVMgram.History.Media.LinkPreview
GRVMgram.History.Media.File
GRVMgram.History.Media.Photo
GRVMgram.History.Media.Game
GRVMgram.History.Media.Paid
GRVMgram.History.Media.Contact
GRVMgram.History.Media.Location
GRVMgram.History.Media.Invoice
GRVMgram.ChatMenu.Title
GRVMgram.ChatMenu.ViewDeleted
GRVMgram.ChatMenu.ClearDeleted
GRVMgram.Menu.LocalHide
GRVMgram.Menu.UserMessages
GRVMgram.Menu.Details
GRVMgram.Menu.Repeat
GRVMgram.Menu.AddFilter
GRVMgram.Menu.ViewFilters
GRVMgram.Menu.History
GRVMgram.Menu.DeleteOwn
GRVMgram.Menu.ReadMessage
GRVMgram.Menu.ReadAllLocal
GRVMgram.Menu.ReadAllServer
GRVMgram.Menu.Burn
GRVMgram.Menu.Replay
GRVMgram.Menu.ForwardLocalCopy
GRVMgram.Menu.SendAsSticker
GRVMgram.Menu.CopyID
GRVMgram.Menu.CopyCallback
GRVMgram.Menu.JumpBeginning
GRVMgram.Menu.OpenProfileID
GRVMgram.Repeat.Unavailable
GRVMgram.Confirm.SendSticker
GRVMgram.Confirm.SendGIF
GRVMgram.Confirm.SendVoice
GRVMgram.StoryGhost.Title
GRVMgram.StoryGhost.Text
GRVMgram.StoryGhost.Enable
GRVMgram.StoryGhost.Open
GRVMgram.MessageDetails.Title
GRVMgram.MessageDetails.PeerID
GRVMgram.MessageDetails.Namespace
GRVMgram.MessageDetails.MessageID
GRVMgram.MessageDetails.StableID
GRVMgram.MessageDetails.Date
GRVMgram.MessageDetails.ThreadID
GRVMgram.MessageDetails.Author
GRVMgram.MessageDetails.ForwardDate
GRVMgram.MessageDetails.ForwardAuthor
GRVMgram.MessageDetails.ForwardSource
GRVMgram.MessageDetails.ForwardSourceMessage
GRVMgram.MessageDetails.ForwardSignature
GRVMgram.MessageDetails.Edited
GRVMgram.MessageDetails.Views
GRVMgram.MessageDetails.Forwards
GRVMgram.MessageDetails.Image
GRVMgram.MessageDetails.File
GRVMgram.MessageDetails.Media
GRVMgram.MessageDetails.File.ID
GRVMgram.MessageDetails.File.MIME
GRVMgram.MessageDetails.File.Name
GRVMgram.MessageDetails.File.Size
GRVMgram.MessageDetails.File.Dimensions
GRVMgram.MessageDetails.File.Duration
GRVMgram.MessageShot.Title
GRVMgram.MessageShot.PreviewAccessibility
GRVMgram.MessageShot.Theme
GRVMgram.MessageShot.Theme.Current
GRVMgram.MessageShot.Theme.Light
GRVMgram.MessageShot.Theme.Dark
GRVMgram.MessageShot.Background
GRVMgram.MessageShot.Date
GRVMgram.MessageShot.Reactions
GRVMgram.MessageShot.Header
GRVMgram.MessageShot.Decorations
GRVMgram.MessageShot.Replies
GRVMgram.MessageShot.Spoilers
GRVMgram.MessageShot.Copy
GRVMgram.MessageShot.Save
GRVMgram.MessageShot.SelectedUnavailable
GRVMgram.MessageShot.RenderFailed
GRVMgram.MessageShot.PhotoAccessNotGranted
GRVMgram.MessageShot.SaveFailed
GRVMgram.MessageShot.Photos.Title
GRVMgram.MessageShot.Photos.Text
GRVMgram.MessageShot.Chat
GRVMgram.MessageShot.QuotedReply
GRVMgram.MessageShot.CustomReaction
GRVMgram.MessageShot.Stars
GRVMgram.MessageShot.Boost
GRVMgram.MessageShot.PhotoUnavailable
GRVMgram.MessageShot.FileUnavailable
GRVMgram.MessageShot.MediaUnavailable
GRVMgram.MessageShot.Reply
GRVMgram.MessageShot.MessageUnavailable
GRVMgram.MessageShot.ReplyMediaUnavailable
GRVMgram.SendAsSticker.Error
GRVMgram.Peer.CopyTelegramID
GRVMgram.Peer.CopyBotAPIID
GRVMgram.Peer.Created
GRVMgram.Peer.Joined
GRVMgram.Other.Title
GRVMgram.Other.Header
GRVMgram.Streamer.Title
GRVMgram.Streamer.Info
GRVMgram.Streamer.Cover
GRVMgram.Streamer.CoverAccessibility
GRVMgram.Crash.Title
GRVMgram.Crash.Info
GRVMgram.Crash.Prompt.Title
GRVMgram.Crash.Prompt.Text
GRVMgram.Crash.Export
GRVMgram.Crash.NotNow
GRVMgram.Crash.NoReports
GRVMgram.Crash.Summary
GRVMgram.Crash.CleanupError
GRVMgram.Crash.ShareError
GRVMgram.Reset.Title
GRVMgram.Reset.Text
GRVMgram.Reset.Action
GRVMgram.DeleteOwn.Title
GRVMgram.DeleteOwn.Text
GRVMgram.DeleteOwn.Action
GRVMgram.DeleteOwn.Result
GRVMgram.DeleteOwn.Error
GRVMgram.Read.Error
GRVMgram.Read.Unavailable
GRVMgram.Callback.CopyFailed
GRVMgram.JumpBeginning.Unavailable
GRVMgram.Burn.Title
GRVMgram.Burn.Text
GRVMgram.Burn.Action
GRVMgram.Burn.Error
GRVMgram.Replay.Unavailable
GRVMgram.Replay.RestoreFailed
GRVMgram.ForwardLocalCopy.Unsupported
GRVMgram.ForwardLocalCopy.Unavailable
GRVMgram.ForwardLocalCopy.RestoreFailed
GRVMgram.ForwardLocalCopy.UploadFailed
""".split()
)

FORMAT_TOKEN = re.compile(r"(?<!%)%(?:\d+\$)?[@diuf]")
ENUM_CASE = re.compile(r'^\s*case\s+\w+\s*=\s*"([^"]+)"', re.MULTILINE)
STRINGS_LINE = re.compile(
    r'^"(?P<key>[^"]+)"\s*=\s*"(?P<value>(?:\\.|[^"\\])*)";$'
)


def decode_value(value: str) -> str:
    escapes = {r"\\": "\\", r'\"': '"', r"\n": "\n", r"\r": "\r", r"\t": "\t"}
    return re.sub(r'\\[\\"nrt]', lambda match: escapes[match.group(0)], value)


def parse_strings(path: Path) -> dict[str, str]:
    text = path.read_bytes().decode("utf-8", errors="strict")
    result: dict[str, str] = {}
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        match = STRINGS_LINE.fullmatch(line)
        if match is None:
            raise AssertionError(f"{path}:{number}: invalid .strings entry")
        key = match.group("key")
        if key in result:
            raise AssertionError(f"{path}:{number}: duplicate key {key}")
        result[key] = decode_value(match.group("value"))
    return result


class GRVMgramLocalizationRequiredFilesTests(unittest.TestCase):
    def test_required_localization_files_exist(self) -> None:
        missing = [str(path) for path in (SWIFT, ENGLISH, RUSSIAN) if not path.is_file()]
        self.assertEqual(missing, [], "missing required localization files")


@unittest.skipUnless(
    all(path.is_file() for path in (SWIFT, ENGLISH, RUSSIAN)),
    "localization scaffold is absent",
)
class GRVMgramLocalizationResourcesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.swift = SWIFT.read_text(encoding="utf-8")
        cls.english = parse_strings(ENGLISH)
        cls.russian = parse_strings(RUSSIAN)

    def test_enum_and_tables_have_the_exact_inventory(self) -> None:
        enum_keys = ENUM_CASE.findall(self.swift)
        self.assertEqual(len(enum_keys), len(set(enum_keys)), "duplicate Swift raw value")
        self.assertEqual(set(enum_keys), EXPECTED_KEYS)
        self.assertEqual(set(self.english), EXPECTED_KEYS)
        self.assertEqual(set(self.russian), EXPECTED_KEYS)
        self.assertTrue(all(self.english.values()))
        self.assertTrue(all(self.russian.values()))
        self.assertFalse(any("\ufffd" in value for value in self.english.values()))
        self.assertFalse(any("\ufffd" in value for value in self.russian.values()))

    def test_format_tokens_match_in_order(self) -> None:
        for key in sorted(EXPECTED_KEYS):
            with self.subTest(key=key):
                self.assertEqual(
                    FORMAT_TOKEN.findall(self.english[key]),
                    FORMAT_TOKEN.findall(self.russian[key]),
                )

    def test_loader_uses_telegram_language_explicit_table_and_english_fallback(self) -> None:
        for token in (
            "import AppBundle",
            "presentationStrings.baseLanguageCode.lowercased()",
            'baseCode == "ru" || baseCode.hasPrefix("ru-")',
            'forResource: "GRVMgram"',
            'ofType: "strings"',
            "forLocalization: languageCode",
            "getAppBundle().path(",
            "private static let english",
            "private static let russian",
            "self.englishValues[key.rawValue]",
            "key.rawValue",
            "Locale(identifier: self.languageCode)",
        ):
            self.assertIn(token, self.swift)
        for forbidden in (
            "Bundle.main",
            "NSLocalizedString",
            "table: nil",
            "Locale.preferredLanguages",
            "preferredLocalizations",
            "localizedString(forKey:",
        ):
            self.assertNotIn(forbidden, self.swift)

        for signature in (
            "public init(_ presentationStrings: PresentationStrings)",
            "public let languageCode: String",
            "public subscript(_ key: GRVMgramStringKey) -> String",
            "public func format(_ key: GRVMgramStringKey, _ arguments: CVarArg...) -> String",
        ):
            self.assertIn(signature, self.swift)

    def test_brand_providers_and_retained_rows_are_exact(self) -> None:
        self.assertEqual(self.english["GRVMgram.Brand.Name"], "GRVMgram")
        self.assertEqual(self.russian["GRVMgram.Brand.Name"], "GRVMgram")
        self.assertEqual(self.english["GRVMgram.Chat.DeletedMark.Default"], "🧹")
        self.assertEqual(self.russian["GRVMgram.Chat.DeletedMark.Default"], "🧹")
        self.assertEqual(self.english["GRVMgram.Chat.EditedMark.Default"], "edited")
        self.assertEqual(self.russian["GRVMgram.Chat.EditedMark.Default"], "изменено")
        providers = (
            "GRVMgram.Translation.Telegram",
            "GRVMgram.Translation.Google",
            "GRVMgram.Translation.Yandex",
        )
        self.assertEqual([self.english[key] for key in providers], ["Telegram", "Google", "Yandex"])
        self.assertEqual([self.russian[key] for key in providers], ["Telegram", "Google", "Яндекс"])
        self.assertNotIn("GRVMgram.Translation.Native", EXPECTED_KEYS)
        self.assertEqual(self.english["GRVMgram.Streamer.Title"], "Streamer Mode")
        self.assertEqual(self.english["GRVMgram.Crash.Export"], "Export Local Logs")
        self.assertEqual(
            self.english["GRVMgram.Appearance.AdaptiveSavedMusicColor"],
            "Adaptive Saved Music Color",
        )
        self.assertEqual(self.english["GRVMgram.Menu.UserMessages"], "User Messages: %@")

    def test_local_log_copy_is_honest_and_local_only(self) -> None:
        info = self.english["GRVMgram.Crash.Info"]
        prompt = self.english["GRVMgram.Crash.Prompt.Text"]
        self.assertIn("local Telegram app logs", info)
        self.assertIn("foreground session ends unexpectedly", info)
        self.assertIn("foreground session ended unexpectedly", prompt)
        self.assertIn("Nothing is uploaded automatically.", info)
        crash_copy = "\n".join(
            value for key, value in self.english.items() if key.startswith("GRVMgram.Crash.")
        ).lower()
        for forbidden in (
            ".ips",
            "symbolicated",
            "send a crash report",
            "sent to",
            "recipient",
            "prepared for sharing",
        ):
            self.assertNotIn(forbidden, crash_copy)

    def test_future_peer_and_preserved_media_actions_are_reserved(self) -> None:
        exact_english = {
            "GRVMgram.Menu.DeleteOwn": "Delete Own Messages",
            "GRVMgram.Menu.ReadMessage": "Read Message",
            "GRVMgram.Menu.ReadAllLocal": "Read All Locally",
            "GRVMgram.Menu.ReadAllServer": "Read All on Server",
            "GRVMgram.Menu.CopyCallback": "Copy Callback Data",
            "GRVMgram.Menu.JumpBeginning": "Jump to Beginning",
            "GRVMgram.Menu.Burn": "Burn",
            "GRVMgram.Menu.Replay": "Replay",
            "GRVMgram.Menu.ForwardLocalCopy": "Forward Local Copy",
        }
        for key, value in exact_english.items():
            self.assertEqual(self.english[key], value)

    def test_current_people_header_and_count_results_are_natural(self) -> None:
        self.assertEqual(self.english["GRVMgram.Filters.People"], "People")
        self.assertEqual(self.russian["GRVMgram.Filters.People"], "Пользователи")
        self.assertEqual(
            self.english["GRVMgram.Deleted.ArchivedResources"],
            "Archived resources: %d",
        )
        self.assertEqual(
            self.english["GRVMgram.DeleteOwn.Result"],
            "Messages deleted: %d.",
        )


if __name__ == "__main__":
    unittest.main()
