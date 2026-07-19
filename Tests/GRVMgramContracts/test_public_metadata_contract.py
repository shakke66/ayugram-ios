import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_PATH = ROOT / "Telegram/BUILD"
CONFIG_PATH = ROOT / "Telegram/Telegram-iOS/Config-Fork.xcconfig"
INFO_PLIST_PATHS = (
    ROOT / "Telegram/Telegram-iOS/ar.lproj/InfoPlist.strings",
    ROOT / "Telegram/Telegram-iOS/ko.lproj/InfoPlist.strings",
)

EXTENSION_PLISTS = {
    "ShareInfoPlist": ".Share",
    "NotificationContentInfoPlist": ".NotificationContent",
    "WidgetInfoPlist": ".Widget",
    "IntentsInfoPlist": ".SiriIntents",
    "BroadcastUploadInfoPlist": ".BroadcastUpload",
    "NotificationServiceInfoPlist": ".NotificationService",
}

PERMISSION_KEYS = {
    "NSContactsUsageDescription",
    "NSLocationWhenInUseUsageDescription",
    "NSLocationAlwaysAndWhenInUseUsageDescription",
    "NSLocationAlwaysUsageDescription",
    "NSCameraUsageDescription",
    "NSPhotoLibraryUsageDescription",
    "NSPhotoLibraryAddUsageDescription",
    "NSMicrophoneUsageDescription",
    "NSSiriUsageDescription",
    "NSFaceIDUsageDescription",
}


def starlark_rule(source: str, rule_type: str, name: str) -> str:
    pattern = re.compile(rf"(?ms)^{re.escape(rule_type)}\(\n.*?^\)$")
    for match in pattern.finditer(source):
        block = match.group(0)
        if re.search(rf'(?m)^\s+name = "{re.escape(name)}"(?:,|$)', block):
            return block
    raise AssertionError(f"Missing {rule_type} rule {name}")


def plist_values(block: str, key: str) -> list[str]:
    return re.findall(
        rf"<key>{re.escape(key)}</key>\s*<string>([^<]+)</string>",
        block,
    )


class PublicMetadataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = BUILD_PATH.read_text(encoding="utf-8")

    def test_main_and_extension_bundle_names_are_publicly_branded(self) -> None:
        app_name = starlark_rule(self.build, "plist_fragment", "AppNameInfoPlist")
        main_info = starlark_rule(self.build, "plist_fragment", "TelegramInfoPlist")
        self.assertEqual(["GRVMgram"], plist_values(app_name, "CFBundleDisplayName"))
        self.assertEqual(["GRVMgram"], plist_values(main_info, "CFBundleDisplayName"))
        self.assertEqual(["GRVMgram"], plist_values(main_info, "CFBundleName"))

        for plist_name, bundle_suffix in EXTENSION_PLISTS.items():
            with self.subTest(plist=plist_name):
                block = starlark_rule(self.build, "plist_fragment", plist_name)
                self.assertEqual(["GRVMgram"], plist_values(block, "CFBundleName"))
                self.assertEqual(
                    [f"{{telegram_bundle_id}}{bundle_suffix}"],
                    plist_values(block, "CFBundleIdentifier"),
                )

    def test_theme_type_description_is_branded_without_changing_identifier(self) -> None:
        main_info = starlark_rule(self.build, "plist_fragment", "TelegramInfoPlist")
        self.assertEqual(
            ["GRVMgram Color Theme File"],
            plist_values(main_info, "UTTypeDescription"),
        )
        self.assertEqual(
            ["org.telegram.Telegram-iOS.theme"],
            plist_values(main_info, "UTTypeIdentifier"),
        )
        self.assertIn("<string>tgios-theme</string>", main_info)

    def test_grvmgram_tables_are_registered_with_stock_resources(self) -> None:
        resources = starlark_rule(self.build, "filegroup", "AppStringResources")
        packaged_strings = re.findall(r'"(Telegram-iOS/[^"\n]+\.strings)"', resources)
        self.assertEqual(
            [
                "Telegram-iOS/en.lproj/Localizable.strings",
                "Telegram-iOS/en.lproj/GRVMgram.strings",
                "Telegram-iOS/ru.lproj/GRVMgram.strings",
            ],
            packaged_strings,
        )
        self.assertIn("empty_languages", resources)

    def test_fork_config_changes_only_public_app_name(self) -> None:
        lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
        assignments = [line.split("=", 1)[0].strip() for line in lines if line.strip()]

        self.assertEqual("APP_NAME=GRVMgram", lines[0])
        self.assertIn("APP_BUNDLE_ID=fork.telegram.Fork", lines)
        self.assertIn("APP_SPECIFIC_URL_SCHEME=tgfork", lines)
        self.assertEqual(
            [
                "APP_NAME",
                "APP_BUNDLE_ID",
                "APP_SPECIFIC_URL_SCHEME",
                "GLOBAL_CONSTANTS",
                "GCC_PREPROCESSOR_DEFINITIONS",
                "GCC_PREPROCESSOR_DEFINITIONS",
            ],
            assignments,
        )

    def test_localized_info_plists_do_not_override_display_name(self) -> None:
        for path in INFO_PLIST_PATHS:
            with self.subTest(locale=path.parent.name):
                contents = path.read_text(encoding="utf-8")
                assignments = re.findall(r'^"([^"]+)"\s*=', contents, re.MULTILINE)
                self.assertNotIn("CFBundleDisplayName", assignments)
                self.assertEqual(PERMISSION_KEYS, set(assignments))
                self.assertEqual(len(PERMISSION_KEYS), len(assignments))

    def test_internal_target_frameworks_and_url_schemes_are_preserved(self) -> None:
        application = starlark_rule(self.build, "ios_application", "Telegram")
        self.assertIn('bundle_id = "{telegram_bundle_id}".format(', application)
        self.assertNotIn("GRVMgram.app", self.build)
        self.assertNotIn("GRVMgram.ipa", self.build)

        for framework in ("TelegramApi", "TelegramCore", "TelegramUI"):
            with self.subTest(framework=framework):
                block = starlark_rule(
                    self.build,
                    "plist_fragment",
                    f"{framework}InfoPlist",
                )
                self.assertEqual([framework], plist_values(block, "CFBundleName"))
                self.assertEqual(
                    [f"{{telegram_bundle_id}}.{framework}"],
                    plist_values(block, "CFBundleIdentifier"),
                )

        url_types = starlark_rule(self.build, "plist_fragment", "UrlTypesInfoPlist")
        self.assertEqual(
            [
                "{telegram_bundle_id}",
                "{telegram_bundle_id}.compatibility",
            ],
            plist_values(url_types, "CFBundleURLName"),
        )
        scheme_arrays = re.findall(
            r"<key>CFBundleURLSchemes</key>\s*<array>(.*?)</array>",
            url_types,
            re.DOTALL,
        )
        self.assertEqual(
            ["telegram", "tg", "tonsite"],
            [
                value
                for array in scheme_arrays
                for value in re.findall(r"<string>([^<]+)</string>", array)
            ],
        )


if __name__ == "__main__":
    unittest.main()
