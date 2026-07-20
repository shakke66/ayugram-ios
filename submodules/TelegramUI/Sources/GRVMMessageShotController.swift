import Foundation
import UIKit
import Photos
import AsyncDisplayKit
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import AccountContext
import AyuGramLib
import AyuGramFeatures
import AlertUI
import PresentationDataUtils

public final class GRVMMessageShotController: ViewController {
    private static let renderQueue = Queue(name: "org.telegram.grvm-message-shot-render", qos: .userInitiated)

    private let context: AccountContext
    private let peerId: PeerId
    private let threadId: Int64?
    private let selectedIds: Set<MessageId>
    private let presentationData: PresentationData
    private let chatTheme: PresentationTheme
    private let chatWallpaper: TelegramWallpaper
    private let strings: PresentationStrings
    private let grvmStrings: GRVMgramStrings
    private let dateTimeFormat: PresentationDateTimeFormat
    private let nameDisplayOrder: PresentationPersonNameOrder
    private let completion: () -> Void

    private var model: GRVMMessageShotModel?
    private var options: GRVMMessageShotOptions?
    private var renderedImage: UIImage?
    private var renderGeneration: UInt = 0
    private var renderedGeneration: UInt?
    private let loadDisposable = MetaDisposable()
    private let settingsDisposable = MetaDisposable()

    private let previewScrollView = UIScrollView()
    private let previewImageView = UIImageView()
    private let controlsScrollView = UIScrollView()
    private let controlsStack = UIStackView()
    private let themeControl: UISegmentedControl
    private let showBackgroundSwitch = UISwitch()
    private let showDateSwitch = UISwitch()
    private let showReactionsSwitch = UISwitch()
    private let showHeaderSwitch = UISwitch()
    private let showHeaderDecorationsSwitch = UISwitch()
    private let colorfulRepliesSwitch = UISwitch()
    private let revealSpoilersSwitch = UISwitch()
    private let showReactionsRow = UIStackView()
    private let showHeaderDecorationsRow = UIStackView()
    private let colorfulRepliesRow = UIStackView()
    private let revealSpoilersRow = UIStackView()
    private let copyButton = UIButton(type: .system)
    private let saveButton = UIButton(type: .system)
    private let activityIndicator = UIActivityIndicatorView(style: .medium)

    public init(
        context: AccountContext,
        peerId: PeerId,
        threadId: Int64?,
        selectedIds: Set<MessageId>,
        presentationData: PresentationData,
        chatTheme: PresentationTheme,
        chatWallpaper: TelegramWallpaper,
        strings: PresentationStrings,
        dateTimeFormat: PresentationDateTimeFormat,
        nameDisplayOrder: PresentationPersonNameOrder,
        completion: @escaping () -> Void
    ) {
        let grvmStrings = GRVMgramStrings(strings)
        self.context = context
        self.peerId = peerId
        self.threadId = threadId
        self.selectedIds = selectedIds
        self.presentationData = presentationData
        self.chatTheme = chatTheme
        self.chatWallpaper = chatWallpaper
        self.strings = strings
        self.grvmStrings = grvmStrings
        self.themeControl = UISegmentedControl(items: [
            grvmStrings[.messageShotThemeCurrent],
            grvmStrings[.messageShotThemeLight],
            grvmStrings[.messageShotThemeDark],
        ])
        self.dateTimeFormat = dateTimeFormat
        self.nameDisplayOrder = nameDisplayOrder
        self.completion = completion
        super.init(navigationBarPresentationData: NavigationBarPresentationData(presentationData: presentationData, style: .glass))
        self.title = self.grvmStrings[.messageShotTitle]
    }

    required init(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    deinit {
        self.loadDisposable.dispose()
        self.settingsDisposable.dispose()
    }

    public override func loadDisplayNode() {
        self.displayNode = ASDisplayNode()
        self.displayNode.backgroundColor = self.presentationData.theme.list.plainBackgroundColor
        self.displayNodeDidLoad()
        self.configureUI()
        self.load()
    }

    private func configureUI() {
        let rootView = self.displayNode.view
        let accentColor = self.presentationData.theme.list.itemAccentColor
        let primaryTextColor = self.presentationData.theme.list.itemPrimaryTextColor

        self.previewScrollView.translatesAutoresizingMaskIntoConstraints = false
        self.previewScrollView.alwaysBounceVertical = true
        self.previewScrollView.backgroundColor = self.presentationData.theme.list.blocksBackgroundColor
        rootView.addSubview(self.previewScrollView)

        self.previewImageView.translatesAutoresizingMaskIntoConstraints = false
        self.previewImageView.contentMode = .scaleAspectFit
        self.previewImageView.accessibilityLabel = self.grvmStrings[.messageShotPreviewAccessibility]
        self.previewScrollView.addSubview(self.previewImageView)

        self.controlsScrollView.translatesAutoresizingMaskIntoConstraints = false
        self.controlsScrollView.alwaysBounceVertical = true
        rootView.addSubview(self.controlsScrollView)

        self.controlsStack.translatesAutoresizingMaskIntoConstraints = false
        self.controlsStack.axis = .vertical
        self.controlsStack.spacing = 10.0
        self.controlsStack.isLayoutMarginsRelativeArrangement = true
        self.controlsStack.layoutMargins = UIEdgeInsets(top: 16.0, left: 16.0, bottom: 16.0, right: 16.0)
        self.controlsScrollView.addSubview(self.controlsStack)

        self.themeControl.selectedSegmentIndex = 0
        self.themeControl.addTarget(self, action: #selector(self.optionControlChanged), for: .valueChanged)
        self.controlsStack.addArrangedSubview(self.themeControl)

        self.controlsStack.addArrangedSubview(self.makeSwitchRow(title: self.grvmStrings[.messageShotBackground], control: self.showBackgroundSwitch))
        self.controlsStack.addArrangedSubview(self.makeSwitchRow(title: self.grvmStrings[.messageShotDate], control: self.showDateSwitch))
        self.configureSwitchRow(self.showReactionsRow, title: self.grvmStrings[.messageShotReactions], control: self.showReactionsSwitch)
        self.controlsStack.addArrangedSubview(self.showReactionsRow)
        self.controlsStack.addArrangedSubview(self.makeSwitchRow(title: self.grvmStrings[.messageShotHeader], control: self.showHeaderSwitch))
        self.configureSwitchRow(self.showHeaderDecorationsRow, title: self.grvmStrings[.messageShotDecorations], control: self.showHeaderDecorationsSwitch)
        self.controlsStack.addArrangedSubview(self.showHeaderDecorationsRow)
        self.configureSwitchRow(self.colorfulRepliesRow, title: self.grvmStrings[.messageShotReplies], control: self.colorfulRepliesSwitch)
        self.controlsStack.addArrangedSubview(self.colorfulRepliesRow)
        self.configureSwitchRow(self.revealSpoilersRow, title: self.grvmStrings[.messageShotSpoilers], control: self.revealSpoilersSwitch)
        self.controlsStack.addArrangedSubview(self.revealSpoilersRow)

        let actions = UIStackView(arrangedSubviews: [self.copyButton, self.saveButton])
        actions.axis = .horizontal
        actions.distribution = .fillEqually
        actions.spacing = 12.0
        self.copyButton.setTitle(self.grvmStrings[.messageShotCopy], for: .normal)
        self.saveButton.setTitle(self.grvmStrings[.messageShotSave], for: .normal)
        self.copyButton.tintColor = accentColor
        self.saveButton.tintColor = accentColor
        self.copyButton.titleLabel?.font = UIFont.systemFont(ofSize: 17.0, weight: .semibold)
        self.saveButton.titleLabel?.font = UIFont.systemFont(ofSize: 17.0, weight: .semibold)
        self.copyButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 44.0).isActive = true
        self.saveButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 44.0).isActive = true
        self.copyButton.addTarget(self, action: #selector(self.copyPressed), for: .touchUpInside)
        self.saveButton.addTarget(self, action: #selector(self.savePressed), for: .touchUpInside)
        self.controlsStack.addArrangedSubview(actions)

        self.activityIndicator.translatesAutoresizingMaskIntoConstraints = false
        self.activityIndicator.color = primaryTextColor
        rootView.addSubview(self.activityIndicator)

        NSLayoutConstraint.activate([
            self.previewScrollView.leadingAnchor.constraint(equalTo: rootView.leadingAnchor),
            self.previewScrollView.topAnchor.constraint(equalTo: rootView.topAnchor),
            self.previewScrollView.trailingAnchor.constraint(equalTo: rootView.trailingAnchor),
            self.previewScrollView.heightAnchor.constraint(equalTo: rootView.heightAnchor, multiplier: 0.52),
            self.controlsScrollView.leadingAnchor.constraint(equalTo: rootView.leadingAnchor),
            self.controlsScrollView.topAnchor.constraint(equalTo: self.previewScrollView.bottomAnchor),
            self.controlsScrollView.trailingAnchor.constraint(equalTo: rootView.trailingAnchor),
            self.controlsScrollView.bottomAnchor.constraint(equalTo: rootView.bottomAnchor),
            self.previewImageView.leadingAnchor.constraint(equalTo: self.previewScrollView.contentLayoutGuide.leadingAnchor, constant: 12.0),
            self.previewImageView.trailingAnchor.constraint(equalTo: self.previewScrollView.contentLayoutGuide.trailingAnchor, constant: -12.0),
            self.previewImageView.topAnchor.constraint(equalTo: self.previewScrollView.contentLayoutGuide.topAnchor, constant: 12.0),
            self.previewImageView.bottomAnchor.constraint(equalTo: self.previewScrollView.contentLayoutGuide.bottomAnchor, constant: -12.0),
            self.previewImageView.widthAnchor.constraint(equalTo: self.previewScrollView.frameLayoutGuide.widthAnchor, constant: -24.0),
            self.previewImageView.heightAnchor.constraint(greaterThanOrEqualToConstant: 120.0),
            self.controlsStack.leadingAnchor.constraint(equalTo: self.controlsScrollView.contentLayoutGuide.leadingAnchor),
            self.controlsStack.trailingAnchor.constraint(equalTo: self.controlsScrollView.contentLayoutGuide.trailingAnchor),
            self.controlsStack.topAnchor.constraint(equalTo: self.controlsScrollView.contentLayoutGuide.topAnchor),
            self.controlsStack.bottomAnchor.constraint(equalTo: self.controlsScrollView.contentLayoutGuide.bottomAnchor),
            self.controlsStack.widthAnchor.constraint(equalTo: self.controlsScrollView.frameLayoutGuide.widthAnchor),
            self.activityIndicator.centerXAnchor.constraint(equalTo: self.previewScrollView.centerXAnchor),
            self.activityIndicator.centerYAnchor.constraint(equalTo: self.previewScrollView.centerYAnchor)
        ])
        self.setActionsEnabled(false)
        self.activityIndicator.startAnimating()
    }

    private func makeSwitchRow(title: String, control: UISwitch) -> UIStackView {
        let row = UIStackView()
        self.configureSwitchRow(row, title: title, control: control)
        return row
    }

    private func configureSwitchRow(_ row: UIStackView, title: String, control: UISwitch) {
        let label = UILabel()
        label.text = title
        label.textColor = self.presentationData.theme.list.itemPrimaryTextColor
        label.font = UIFont.systemFont(ofSize: 16.0)
        row.axis = .horizontal
        row.alignment = .center
        row.distribution = .fill
        row.spacing = 12.0
        row.addArrangedSubview(label)
        row.addArrangedSubview(control)
        row.heightAnchor.constraint(greaterThanOrEqualToConstant: 44.0).isActive = true
        control.addTarget(self, action: #selector(self.optionControlChanged), for: .valueChanged)
    }

    private func load() {
        let modelSignal = GRVMMessageShotModel.load(
            postbox: self.context.account.postbox,
            accountPeerId: self.context.account.peerId,
            peerId: self.peerId,
            threadId: self.threadId,
            selectedIds: self.selectedIds,
            strings: self.strings,
            dateTimeFormat: self.dateTimeFormat,
            nameDisplayOrder: self.nameDisplayOrder
        )
        let settingsSignal = grvmSettings(
            accountId: self.context.account.peerId,
            accountManager: self.context.sharedContext.accountManager
        )
        self.loadDisposable.set((combineLatest(modelSignal, settingsSignal)
        |> take(1)
        |> deliverOnMainQueue).startStrict(next: { [weak self] modelResult, settings in
            guard let self else {
                return
            }
            switch modelResult {
            case let .success(model):
                self.model = model
                self.options = settings.grvmChatAppearanceSettings.messageShot
                self.applyOptionsToControls()
                self.applyCapabilities(model.capabilities)
                self.requestRender()
            case .failure:
                self.activityIndicator.stopAnimating()
                self.presentError(self.grvmStrings[.messageShotSelectedUnavailable])
            }
        }))
    }

    private func applyOptionsToControls() {
        guard let options = self.options else {
            return
        }
        self.themeControl.selectedSegmentIndex = Int(options.theme.rawValue)
        self.showBackgroundSwitch.isOn = options.showBackground
        self.showDateSwitch.isOn = options.showDate
        self.showReactionsSwitch.isOn = options.showReactions
        self.showHeaderSwitch.isOn = options.showHeader
        self.showHeaderDecorationsSwitch.isOn = options.showHeaderDecorations
        self.colorfulRepliesSwitch.isOn = options.colorfulReplies
        self.revealSpoilersSwitch.isOn = options.revealSpoilers
    }

    private func applyCapabilities(_ capabilities: GRVMMessageShotCapabilities) {
        self.showReactionsRow.isHidden = !capabilities.hasReactions
        self.colorfulRepliesRow.isHidden = !capabilities.hasReplies
        self.revealSpoilersRow.isHidden = !capabilities.hasSpoilers
        self.showHeaderDecorationsRow.isHidden = !capabilities.hasHeaderDecorations
    }

    @objc private func optionControlChanged() {
        guard let theme = GRVMMessageShotTheme(rawValue: Int32(self.themeControl.selectedSegmentIndex)) else {
            return
        }
        self.updateOptions(GRVMMessageShotOptions(
            showBackground: self.showBackgroundSwitch.isOn,
            showDate: self.showDateSwitch.isOn,
            showReactions: self.showReactionsSwitch.isOn,
            showHeader: self.showHeaderSwitch.isOn,
            showHeaderDecorations: self.showHeaderDecorationsSwitch.isOn,
            colorfulReplies: self.colorfulRepliesSwitch.isOn,
            revealSpoilers: self.revealSpoilersSwitch.isOn,
            theme: theme
        ))
    }

    private func updateOptions(_ options: GRVMMessageShotOptions) {
        guard self.options != options else {
            return
        }
        self.options = options
        self.settingsDisposable.set(updateGRVMSettings(
            accountId: self.context.account.peerId,
            accountManager: self.context.sharedContext.accountManager,
            { settings in
                var settings = settings
                settings.messageShotShowBackground = options.showBackground
                settings.messageShotShowDate = options.showDate
                settings.messageShotShowReactions = options.showReactions
                settings.messageShotShowHeader = options.showHeader
                settings.messageShotShowHeaderDecorations = options.showHeaderDecorations
                settings.messageShotColorfulReplies = options.colorfulReplies
                settings.messageShotRevealSpoilers = options.revealSpoilers
                settings.messageShotTheme = options.theme.rawValue
                return settings
            }
        ).startStrict())
        self.requestRender()
    }

    private func requestRender() {
        guard let model = self.model, let options = self.options else {
            return
        }
        self.renderGeneration &+= 1
        let generation = self.renderGeneration
        self.renderedGeneration = nil
        self.renderedImage = nil
        self.setActionsEnabled(false)
        self.activityIndicator.startAnimating()
        let renderer = GRVMMessageShotRenderer(
            model: model,
            options: options,
            theme: self.chatTheme,
            wallpaper: self.chatWallpaper,
            strings: self.grvmStrings
        )
        GRVMMessageShotController.renderQueue.async { [weak self] in
            let result: Result<UIImage, Error> = autoreleasepool {
                do {
                    return .success(try renderer.render(scale: GRVMMessageShotRenderer.defaultScale))
                } catch {
                    return .failure(error)
                }
            }
            Queue.mainQueue().async {
                guard let self else {
                    return
                }
                guard generation == self.renderGeneration else {
                    return
                }
                self.activityIndicator.stopAnimating()
                switch result {
                case let .success(image):
                    self.renderedImage = image
                    self.renderedGeneration = generation
                    self.previewImageView.image = image
                    self.setActionsEnabled(true)
                case .failure:
                    self.previewImageView.image = nil
                    self.presentError(self.grvmStrings[.messageShotRenderFailed])
                }
            }
        }
    }

    private func setActionsEnabled(_ enabled: Bool) {
        self.copyButton.isEnabled = enabled
        self.saveButton.isEnabled = enabled
        self.copyButton.alpha = enabled ? 1.0 : 0.5
        self.saveButton.alpha = enabled ? 1.0 : 0.5
    }

    @objc private func copyPressed() {
        guard self.renderedGeneration == self.renderGeneration,
              let image = self.renderedImage,
              let data = image.pngData() else {
            return
        }
        UIPasteboard.general.setData(data, forPasteboardType: "public.png")
        self.completion()
        self.dismiss()
    }

    @objc private func savePressed() {
        guard self.renderedGeneration == self.renderGeneration,
              let image = self.renderedImage,
              let pngData = image.pngData() else {
            return
        }
        self.requestPhotoAuthorization { [weak self] status in
            guard let self else {
                return
            }
            switch status {
            case .authorized, .limited:
                self.saveToPhotos(pngData: pngData)
            case .denied, .restricted:
                self.presentPhotoAccessDenied()
            case .notDetermined:
                self.presentError(self.grvmStrings[.messageShotPhotoAccessNotGranted])
            @unknown default:
                self.presentError(self.grvmStrings[.messageShotPhotoAccessNotGranted])
            }
        }
    }

    private func requestPhotoAuthorization(_ completion: @escaping (PHAuthorizationStatus) -> Void) {
        if #available(iOS 14.0, *) {
            let status = PHPhotoLibrary.authorizationStatus(for: .addOnly)
            if status == .notDetermined {
                PHPhotoLibrary.requestAuthorization(for: .addOnly) { status in
                    Queue.mainQueue().async {
                        completion(status)
                    }
                }
            } else {
                Queue.mainQueue().async {
                    completion(status)
                }
            }
        } else {
            let status = PHPhotoLibrary.authorizationStatus()
            if status == .notDetermined {
                PHPhotoLibrary.requestAuthorization { status in
                    Queue.mainQueue().async {
                        completion(status)
                    }
                }
            } else {
                Queue.mainQueue().async {
                    completion(status)
                }
            }
        }
    }

    private func saveToPhotos(pngData: Data) {
        PHPhotoLibrary.shared().performChanges({
            let creationRequest = PHAssetCreationRequest.forAsset()
            creationRequest.addResource(with: .photo, data: pngData, options: nil)
        }, completionHandler: { [weak self] success, error in
            Queue.mainQueue().async {
                guard let self else {
                    return
                }
                if success {
                    self.completion()
                    self.dismiss()
                } else {
                    self.presentError(error?.localizedDescription ?? self.grvmStrings[.messageShotSaveFailed])
                }
            }
        })
    }

    private func presentPhotoAccessDenied() {
        let controller = textAlertController(context: self.context, title: self.grvmStrings[.messageShotPhotosTitle], text: self.grvmStrings[.messageShotPhotosText], actions: [
            TextAlertAction(type: .defaultAction, title: self.strings.Common_Cancel, action: {}),
            TextAlertAction(type: .genericAction, title: self.strings.Settings_Title, action: {
                guard let url = URL(string: UIApplication.openSettingsURLString) else {
                    return
                }
                UIApplication.shared.open(url)
            })
        ])
        self.present(controller, in: .window(.root))
    }

    private func presentError(_ text: String) {
        let controller = textAlertController(context: self.context, title: self.grvmStrings[.messageShotTitle], text: text, actions: [TextAlertAction(type: .defaultAction, title: self.strings.Common_OK, action: {})])
        self.present(controller, in: .window(.root))
    }
}
