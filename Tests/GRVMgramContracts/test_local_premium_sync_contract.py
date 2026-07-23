import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


class LocalPremiumSyncContractTests(unittest.TestCase):
    def test_outgoing_encoder_is_opt_in_and_preserves_stock_entities(self) -> None:
        encoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/TextEntitiesMessageAttribute.swift"
        )
        function = swift_block(encoder, "func apiEntitiesFromMessageTextEntities(")
        self.assertIn("localPremiumEmojiTransport", function)
        self.assertIn("serverAllowedFileIds", function)
        self.assertIn('url: "tg://emoji?id=\\(fileId)"', function)
        self.assertIn(".messageEntityTextUrl", function)
        self.assertIn(".messageEntityCustomEmoji", function)
        self.assertRegex(
            function,
            r"localPremiumEmojiTransport\.enabled\s*&&\s*fileId\s*>\s*0\s*&&\s*!localPremiumEmojiTransport\.serverAllowedFileIds\.contains\(fileId\)",
        )

    def test_send_gate_uses_exact_account_raw_premium_and_channel_allowlist(self) -> None:
        encoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/TextEntitiesMessageAttribute.swift"
        )
        policy = swift_block(encoder, "func grvmLocalPremiumEmojiTransport(")
        for token in (
            "peerId != accountPeerId",
            "AyuGramHooks.isLocalPremiumEnabled?(accountPeerId) == true",
            "transaction.getPeer(accountPeerId) as? TelegramUser",
            "accountUser.flags.contains(.isPremium)",
            "transaction.getPeerCachedData(peerId: peerId) as? CachedChannelData",
            "cachedData.emojiPack",
            "transaction.getItemCollectionItems(collectionId: emojiPack.id)",
            "item.file.fileId.id",
        ):
            self.assertIn(token, policy)
        self.assertNotIn("accountUser.isPremium", policy)

        pending = source(
            "submodules/TelegramCore/Sources/State/PendingMessageManager.swift"
        )
        self.assertEqual(pending.count("grvmLocalPremiumEmojiTransport("), 2)
        self.assertGreaterEqual(
            pending.count("localPremiumEmojiTransport: grvmEmojiTransport"),
            2,
        )

    def test_edit_path_uses_the_same_transport_policy(self) -> None:
        edit = source(
            "submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift"
        )
        self.assertIn("GRVMLocalPremiumEmojiTransport", edit)
        self.assertIn("grvmLocalPremiumEmojiTransport(", edit)
        self.assertIn("localPremiumEmojiTransport: grvmEmojiTransport", edit)

    def test_reply_quotes_use_the_same_transport_snapshot_on_every_send_route(self) -> None:
        pending = source(
            "submodules/TelegramCore/Sources/State/PendingMessageManager.swift"
        )
        quote_calls = re.findall(
            r"quoteEntities\s*=\s*apiEntitiesFromMessageTextEntities\(\s*"
            r"replyQuote\.entities,\s*associatedPeers:\s*associatedPeers,\s*"
            r"localPremiumEmojiTransport:\s*grvmEmojiTransport\s*\)",
            pending,
        )
        self.assertEqual(4, len(quote_calls))
        self.assertEqual(
            4,
            pending.count("quoteEntities = apiEntitiesFromMessageTextEntities("),
        )

    def test_incoming_decoder_requires_exact_url_range_and_single_emoji(self) -> None:
        decoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/StoreMessage_Telegram.swift"
        )
        url_parser = swift_block(decoder, "private func grvmLocalPremiumEmojiFileId(")
        for token in (
            'let prefix = "tg://emoji?id="',
            "url.hasPrefix(prefix)",
            "48 ... 57",
            "Int64(rawFileId)",
            "fileId > 0",
        ):
            self.assertIn(token, url_parser)

        emoji_guard = swift_block(decoder, "private func grvmIsSingleUnicodeEmoji(")
        self.assertIn("value.count == 1", emoji_guard)
        self.assertIn("value.containsEmoji", emoji_guard)

        conversion = swift_block(decoder, "private func grvmLocalPremiumEmojiEntity(")
        for token in (
            "offset >= 0",
            "length > 0",
            "NSMaxRange(range) <= nsText.length",
            "nsText.substring(with: range)",
            "grvmIsSingleUnicodeEmoji(entityText)",
            ".CustomEmoji(stickerPack: nil, fileId: fileId)",
        ):
            self.assertIn(token, conversion)

        entities = swift_block(decoder, "func messageTextEntitiesFromApiEntities(")
        self.assertIn("text: String? = nil", entities)
        text_url_case = entities[
            entities.index("case let .messageEntityTextUrl") : entities.index(
                "case let .messageEntityMentionName"
            )
        ]
        self.assertIn("grvmLocalPremiumEmojiEntity", text_url_case)
        self.assertIn(".TextUrl(url: url)", text_url_case)

    def test_store_message_supplies_text_to_the_decoder(self) -> None:
        store = source(
            "submodules/TelegramCore/Sources/ApiUtils/StoreMessage_Telegram.swift"
        )
        self.assertIn(
            "messageTextEntitiesFromApiEntities(entities, text: messageText)", store
        )
        self.assertGreaterEqual(
            len(
                re.findall(
                    r"messageTextEntitiesFromApiEntities\(quoteEntities \?\? \[\], text: quoteText \?\? \"\"\)",
                    store,
                )
            ),
            3,
        )

    def test_short_sent_ack_supplies_current_text_to_the_decoder(self) -> None:
        apply_update = source(
            "submodules/TelegramCore/Sources/State/ApplyUpdateMessage.swift"
        )
        short_sent = apply_update[
            apply_update.index("case let .updateShortSentMessage") :
            apply_update.index("if Namespaces.Message.allQuickReply", apply_update.index("case let .updateShortSentMessage"))
        ]
        self.assertIn(
            "messageTextEntitiesFromApiEntities(entities, text: currentMessage.text)",
            short_sent,
        )
        self.assertNotIn(
            "messageTextEntitiesFromApiEntities(entities)", short_sent
        )


if __name__ == "__main__":
    unittest.main()
