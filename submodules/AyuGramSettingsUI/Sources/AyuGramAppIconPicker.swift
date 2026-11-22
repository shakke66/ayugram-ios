import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramPresentationData
import AccountContext

private let grvmAppIconTitleKeys: [String: GRVMgramStringKey] = [
    "default": .appIconDefault,
    "Black": .appIconBlack,
    "BlackIcon": .appIconBlack,
    "BlackClassic": .appIconBlackClassic,
    "BlackClassicIcon": .appIconBlackClassic,
    "BlackFilled": .appIconBlackFilled,
    "BlackFilledIcon": .appIconBlackFilled,
    "Blue": .appIconBlue,
    "BlueIcon": .appIconBlue,
    "BlueClassic": .appIconBlueClassic,
    "BlueClassicIcon": .appIconBlueClassic,
    "BlueFilled": .appIconBlueFilled,
    "BlueFilledIcon": .appIconBlueFilled,
    "WhiteFilled": .appIconWhiteFilled,
    "WhiteFilledIcon": .appIconWhiteFilled,
    "New1": .appIconNew1,
    "New2": .appIconNew2,
    "Premium": .appIconPremium,
    "PremiumBlack": .appIconPremiumBlack,
    "PremiumTurbo": .appIconPremiumTurbo,
]

public func grvmAppIconDisplayTitle(_ identifier: String, strings: GRVMgramStrings) -> String {
    if let key = grvmAppIconTitleKeys[identifier] {
        return strings[key]
    } else {
        return strings[.appIconTitle]
    }
}

public func ayuGramAppIconPicker(
    context: AccountContext,
    onSelect: @escaping (String) -> Void
) -> ViewController {
    let presentationData = context.sharedContext.currentPresentationData.with { $0 }
    let strings = GRVMgramStrings(presentationData.strings)
    let controller = ActionSheetController(presentationData: presentationData)
    let icons = context.sharedContext.applicationBindings.getAvailableAlternateIcons()
    let currentName = context.sharedContext.applicationBindings.getAlternateIconName()
    var requestInFlight = false

    let iconItems: [ActionSheetItem] = icons.map { icon in
        let displayIdentifier = icon.isDefault ? "default" : icon.name
        let title = grvmAppIconDisplayTitle(displayIdentifier, strings: strings)
        let isCurrent = icon.isDefault ? currentName == nil : icon.name == currentName
        let storedIdentifier = icon.isDefault ? "default" : icon.name

        return ActionSheetButtonItem(
            title: isCurrent ? "\u{2713} \(title)" : title,
            color: .accent,
            action: { [weak controller] in
                guard !requestInFlight else {
                    return
                }
                requestInFlight = true
                context.sharedContext.applicationBindings.requestSetAlternateIconName(icon.isDefault ? nil : icon.name) { success in
                    Queue.mainQueue().async {
                        requestInFlight = false
                        guard success else {
                            return
                        }
                        onSelect(storedIdentifier)
                        controller?.dismissAnimated()
                    }
                }
            }
        )
    }

    controller.setItemGroups([
        ActionSheetItemGroup(items: iconItems),
        ActionSheetItemGroup(items: [
            ActionSheetButtonItem(
                title: presentationData.strings.Common_Cancel,
                color: .accent,
                action: { [weak controller] in
                    controller?.dismissAnimated()
                }
            )
        ])
    ])
    return controller
}
