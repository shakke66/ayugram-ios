import UIKit
import SwiftSignalKit

final class GRVMScreenCapturePrivacyController {
    private weak var window: UIWindow?
    private let settingsDisposable = MetaDisposable()
    private var notificationToken: NSObjectProtocol?
    private var coverView: UIView?
    private var isEnabled = false
    private var isDisposed = false

    init(window: UIWindow, enabled: Signal<Bool, NoError>) {
        self.window = window
        self.setEnabledSignal(enabled)

        if #available(iOS 11.0, *) {
            self.notificationToken = NotificationCenter.default.addObserver(
                forName: UIScreen.capturedDidChangeNotification,
                object: nil,
                queue: .main,
                using: { [weak self] _ in
                    self?.refreshCaptureState()
                }
            )
        }
        self.refreshCaptureState()
    }

    static func shouldShowCover(enabled: Bool, isCaptured: Bool) -> Bool {
        return enabled && isCaptured
    }

    func setEnabledSignal(_ enabled: Signal<Bool, NoError>) {
        self.settingsDisposable.set((enabled
        |> distinctUntilChanged
        |> deliverOnMainQueue).start(next: { [weak self] enabled in
            guard let self, !self.isDisposed else {
                return
            }
            self.isEnabled = enabled
            self.refreshCaptureState()
        }))
    }

    func refreshCaptureState() {
        guard !self.isDisposed else {
            return
        }
        let isCaptured: Bool
        if #available(iOS 11.0, *) {
            if let window = self.window {
                isCaptured = window.screen.isCaptured
            } else {
                isCaptured = UIScreen.main.isCaptured
            }
        } else {
            isCaptured = false
        }
        self.updateCoverVisibility(isVisible: Self.shouldShowCover(enabled: self.isEnabled, isCaptured: isCaptured))
    }

    private func updateCoverVisibility(isVisible: Bool) {
        guard let window = self.window else {
            self.coverView?.removeFromSuperview()
            self.coverView = nil
            return
        }
        if isVisible {
            guard self.coverView == nil else {
                return
            }
            let coverView = UIView(frame: window.bounds)
            coverView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            coverView.backgroundColor = .black
            coverView.isOpaque = true
            coverView.isUserInteractionEnabled = true
            coverView.isAccessibilityElement = true
            coverView.accessibilityViewIsModal = true
            coverView.accessibilityLabel = NSLocalizedString(
                "GRVMgram.StreamerPrivacy.Cover",
                value: "GRVMgram Privacy. App content is hidden while the screen is being shared or recorded.",
                comment: "Accessibility label for the screen-capture privacy cover"
            )

            let label = UILabel()
            label.translatesAutoresizingMaskIntoConstraints = false
            label.text = NSLocalizedString(
                "GRVMgram.StreamerPrivacy.Cover",
                value: "GRVMgram Privacy\nApp content is hidden while the screen is being shared or recorded.",
                comment: "Text displayed over app content during public iOS screen capture"
            )
            label.textColor = .white
            label.font = UIFont.preferredFont(forTextStyle: .headline)
            label.adjustsFontForContentSizeCategory = true
            label.numberOfLines = 0
            label.textAlignment = .center
            label.isAccessibilityElement = false
            coverView.addSubview(label)
            NSLayoutConstraint.activate([
                label.centerXAnchor.constraint(equalTo: coverView.centerXAnchor),
                label.centerYAnchor.constraint(equalTo: coverView.centerYAnchor),
                label.leadingAnchor.constraint(greaterThanOrEqualTo: coverView.leadingAnchor, constant: 24.0),
                label.trailingAnchor.constraint(lessThanOrEqualTo: coverView.trailingAnchor, constant: -24.0),
            ])

            self.coverView = coverView
            window.addSubview(coverView)
            UIAccessibility.post(notification: .screenChanged, argument: coverView)
        } else if let coverView = self.coverView {
            self.coverView = nil
            coverView.removeFromSuperview()
        }
    }

    func dispose() {
        guard !self.isDisposed else {
            return
        }
        self.isDisposed = true
        if let notificationToken = self.notificationToken {
            NotificationCenter.default.removeObserver(notificationToken)
            self.notificationToken = nil
        }
        self.settingsDisposable.dispose()
        self.coverView?.removeFromSuperview()
        self.coverView = nil
    }

    deinit {
        self.dispose()
    }
}
