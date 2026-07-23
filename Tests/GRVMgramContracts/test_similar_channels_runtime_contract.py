import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHANNEL_RECOMMENDATION = (
    ROOT
    / "submodules/TelegramCore/Sources/TelegramEngine/Peers/ChannelRecommendation.swift"
)
HOOKS = ROOT / "submodules/TelegramCore/Sources/AyuGramHooks.swift"
FEATURE_MANAGER = (
    ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
)
FEATURE_REGISTRY = (
    ROOT / "submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift"
)
BOT_RECOMMENDATION = (
    ROOT
    / "submodules/TelegramCore/Sources/TelegramEngine/Peers/BotRecomendation.swift"
)
PEER_SEARCH = (
    ROOT / "submodules/TelegramCore/Sources/TelegramEngine/Peers/SearchPeers.swift"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def swift_block(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = source.index("{", start)
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


class SimilarChannelsOwnerSafeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.channel_recommendation = read(CHANNEL_RECOMMENDATION)

    def test_gate_reads_the_exact_account_snapshot(self) -> None:
        gate = swift_block(
            self.channel_recommendation,
            "private func grvmShouldDisableChannelRecommendations(",
        )
        self.assertIn(
            "AyuGramHooks.shouldDisableSimilarChannels?(account.peerId) == true",
            gate,
        )

    def test_disabled_request_stops_before_cache_read_and_network_start(self) -> None:
        request = swift_block(
            self.channel_recommendation,
            "func _internal_requestRecommendedChannels(",
        )
        cache_read = request.index("return account.postbox.transaction")
        network_start = request.index("return account.network.request")
        preflight = request[:cache_read]
        self.assertIn("grvmSimilarChannelsDisabled(account: account)", preflight)
        self.assertIn("|> mapToSignal { disabled", preflight)
        self.assertIn("if disabled", preflight)
        transaction = request[cache_read:network_start]
        self.assertIn(
            "if grvmShouldDisableChannelRecommendations(account: account)",
            transaction,
        )
        self.assertLess(
            request.index("if disabled"),
            cache_read,
        )

    def test_late_response_is_stopped_before_cache_transaction_and_write(self) -> None:
        request = swift_block(
            self.channel_recommendation,
            "func _internal_requestRecommendedChannels(",
        )
        response_start = request.index("|> mapToSignal { result")
        response = request[response_start:]
        cache_transaction = response.index("return account.postbox.transaction")
        cache_write = response.index("transaction.putItemCacheEntry")
        self.assertIn(
            "if grvmShouldDisableChannelRecommendations(account: account)",
            response[:cache_transaction],
        )
        self.assertIn(
            "guard !grvmShouldDisableChannelRecommendations(account: account) else",
            response[cache_transaction:cache_write],
        )
        peer_update = response.index("updatePeers(", cache_transaction)
        self.assertIn(
            "guard !grvmShouldDisableChannelRecommendations(account: account) else",
            response[peer_update:cache_write],
            "The recommendation cache write needs a final setting recheck.",
        )

    def test_disabled_cached_queries_return_nil_before_reading_cache(self) -> None:
        for signature in (
            "func _internal_recommendedChannelPeerIds(",
            "func _internal_recommendedChannels(",
        ):
            with self.subTest(signature=signature):
                query = swift_block(self.channel_recommendation, signature)
                cache_read = query.index("return account.postbox.combinedView")
                preflight = query[:cache_read]
                self.assertIn(
                    "grvmSimilarChannelsDisabled(account: account)", preflight
                )
                self.assertIn("|> mapToSignal { disabled", preflight)
                self.assertIn("if disabled", preflight)
                self.assertIn("return .single(nil)", preflight)
                self.assertIn(
                    "if grvmShouldDisableChannelRecommendations(account: account)",
                    query[cache_read:],
                )

    def test_apps_bots_and_ordinary_peer_search_are_not_gated(self) -> None:
        for signature in (
            "func _internal_requestRecommendedApps(",
            "func _internal_recommendedAppPeerIds(",
        ):
            with self.subTest(signature=signature):
                block = swift_block(self.channel_recommendation, signature)
                self.assertNotIn("grvmShouldDisableChannelRecommendations", block)
                self.assertNotIn("shouldDisableSimilarChannels", block)
        for path in (BOT_RECOMMENDATION, PEER_SEARCH):
            with self.subTest(path=path.name):
                source = read(path)
                self.assertNotIn("grvmShouldDisableChannelRecommendations", source)
                self.assertNotIn("shouldDisableSimilarChannels", source)


class SimilarChannelsReactiveBlockerContractTests(unittest.TestCase):
    def test_inflight_request_has_account_scoped_reactive_disable_provider(self) -> None:
        hooks = read(HOOKS)
        manager = read(FEATURE_MANAGER)
        registry = read(FEATURE_REGISTRY)
        channel_recommendation = read(CHANNEL_RECOMMENDATION)

        reactive_hook_signature = (
            "public static var similarChannelsDisabled: "
            "((PeerId) -> Signal<Bool, NoError>)?"
        )
        self.assertTrue(
            reactive_hook_signature in hooks,
            f"Missing reactive hook: {reactive_hook_signature}",
        )
        self.assertIn("AyuGramHooks.similarChannelsDisabled =", manager)
        registry_provider = swift_block(
            registry,
            "public func similarChannelsDisabled(",
        )
        self.assertIn("accountPeerId: PeerId", registry_provider)
        self.assertIn("Signal<Bool, NoError>", registry_provider)
        self.assertIn("disableSimilarChannels", registry_provider)
        manager_provider = swift_block(
            manager,
            "AyuGramHooks.similarChannelsDisabled =",
        )
        self.assertIn(
            "registry.similarChannelsDisabled(accountPeerId: accountPeerId)",
            manager_provider,
        )
        signal_provider = swift_block(
            channel_recommendation,
            "private func grvmSimilarChannelsDisabled(",
        )
        self.assertIn("AyuGramHooks.similarChannelsDisabled?(account.peerId)", signal_provider)
        self.assertIn(
            "grvmShouldDisableChannelRecommendations(account: account)",
            signal_provider,
        )
        for signature in (
            "func _internal_requestRecommendedChannels(",
            "func _internal_recommendedChannelPeerIds(",
            "func _internal_recommendedChannels(",
        ):
            with self.subTest(signature=signature):
                block = swift_block(channel_recommendation, signature)
                self.assertIn("grvmSimilarChannelsDisabled(account: account)", block)
                self.assertIn("|> mapToSignal { disabled", block)


if __name__ == "__main__":
    unittest.main()
