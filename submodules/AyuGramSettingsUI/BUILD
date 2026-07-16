load("@build_bazel_rules_swift//swift:swift.bzl", "swift_library")

swift_library(
    name = "AyuGramSettingsUI",
    module_name = "AyuGramSettingsUI",
    srcs = glob([
        "Sources/**/*.swift",
    ]),
    copts = [
        "-warnings-as-errors",
    ],
    deps = [
        "//submodules/SSignalKit/SwiftSignalKit:SwiftSignalKit",
        "//submodules/Display:Display",
        "//submodules/Postbox:Postbox",
        "//submodules/TelegramCore:TelegramCore",
        "//submodules/TelegramPresentationData:TelegramPresentationData",
        "//submodules/TelegramUIPreferences:TelegramUIPreferences",
        "//submodules/ItemListUI:ItemListUI",
        "//submodules/AlertUI:AlertUI",
        "//submodules/TranslateUI:TranslateUI",
        "//submodules/PresentationDataUtils:PresentationDataUtils",
        "//submodules/AccountContext:AccountContext",
        "//submodules/AyuGramFeatures:AyuGramFeatures",
        "//submodules/AyuGramLib:AyuGramLib",
        "//submodules/ContextUI:ContextUI",
        "//submodules/TextFormat:TextFormat",
        "//submodules/OverlayStatusController:OverlayStatusController",
    ],
    visibility = [
        "//visibility:public",
    ],
)
