import Foundation
import Postbox
import SwiftSignalKit
import TelegramCore

public struct GRVMLocalCrashExportBundle {
    public let urls: [URL]
    public let fileCount: Int
    public let totalBytes: Int64

    fileprivate let directoryURL: URL

    fileprivate init(urls: [URL], fileCount: Int, totalBytes: Int64, directoryURL: URL) {
        self.urls = urls
        self.fileCount = fileCount
        self.totalBytes = totalBytes
        self.directoryURL = directoryURL
    }
}

private struct GRVMLocalCrashSessionMarker: Codable {
    let accountPeerId: Int64
    let foregroundStartedAt: Double
    let active: Bool
}

private struct GRVMLocalCrashLogCandidate {
    let url: URL
    let fileSize: Int64
    let date: Date
}

public final class GRVMLocalCrashExport {
    private let canonicalRootURL: URL
    private let markerDirectoryURL: URL
    private let markerURL: URL
    private let markerLock = NSLock()

    public init(rootPath: String) {
        let rootURL = URL(fileURLWithPath: rootPath, isDirectory: true)
            .standardizedFileURL
            .resolvingSymlinksInPath()
        let markerDirectoryURL = rootURL.appendingPathComponent("grvm-local-crash", isDirectory: true)
        self.canonicalRootURL = rootURL
        self.markerDirectoryURL = markerDirectoryURL
        self.markerURL = markerDirectoryURL.appendingPathComponent("session.json", isDirectory: false)
    }

    public func beginForegroundSession(accountPeerId: PeerId) {
        self.withMarkerLock {
            self.writeMarker(GRVMLocalCrashSessionMarker(
                accountPeerId: accountPeerId.toInt64(),
                foregroundStartedAt: Date().timeIntervalSince1970,
                active: true
            ))
        }
    }

    public func markSessionClean() {
        self.withMarkerLock {
            guard let marker = self.readMarker() else {
                return
            }
            self.writeMarker(GRVMLocalCrashSessionMarker(
                accountPeerId: marker.accountPeerId,
                foregroundStartedAt: marker.foregroundStartedAt,
                active: false
            ))
        }
    }

    public func previousSessionEndedUnexpectedly(accountPeerId: PeerId) -> Bool {
        return self.withMarkerLock {
            guard let marker = self.readMarker() else {
                return false
            }
            return marker.active && marker.accountPeerId == accountPeerId.toInt64()
        }
    }

    public func stageExport() -> Signal<GRVMLocalCrashExportBundle?, NoError> {
        Logger.shared.sync()
        return combineLatest(
            Logger.shared.collectLogs(),
            Logger.shared.collectShortLogFiles()
        )
        |> map { [weak self] logs, shortLogs -> GRVMLocalCrashExportBundle? in
            guard let self else {
                return nil
            }
            return self.stage(logPaths: (logs + shortLogs).map { $0.1 })
        }
    }

    public func cleanup(_ bundle: GRVMLocalCrashExportBundle) {
        let _ = try? FileManager.default.removeItem(at: bundle.directoryURL)
    }

    func removeSessionMarker() {
        self.withMarkerLock {
            let _ = try? FileManager.default.removeItem(at: self.markerURL)
        }
    }

    private func withMarkerLock<T>(_ f: () -> T) -> T {
        self.markerLock.lock()
        defer {
            self.markerLock.unlock()
        }
        return f()
    }

    private func readMarker() -> GRVMLocalCrashSessionMarker? {
        guard let data = try? Data(contentsOf: self.markerURL) else {
            return nil
        }
        return try? JSONDecoder().decode(GRVMLocalCrashSessionMarker.self, from: data)
    }

    private func writeMarker(_ marker: GRVMLocalCrashSessionMarker) {
        guard let data = try? JSONEncoder().encode(marker) else {
            return
        }
        do {
            try FileManager.default.createDirectory(
                at: self.markerDirectoryURL,
                withIntermediateDirectories: true,
                attributes: nil
            )
            try data.write(to: self.markerURL, options: .atomic)
        } catch {
        }
    }

    private func stage(logPaths: [String]) -> GRVMLocalCrashExportBundle? {
        let maximumFileCount = 8
        let maximumTotalBytes: Int64 = 16 * 1024 * 1024
        var seenPaths = Set<String>()
        var candidates: [GRVMLocalCrashLogCandidate] = []

        for path in logPaths {
            guard let candidate = self.safeCandidate(path: path) else {
                continue
            }
            guard seenPaths.insert(candidate.url.path).inserted else {
                continue
            }
            candidates.append(candidate)
        }
        candidates.sort { lhs, rhs in
            return lhs.date > rhs.date
        }

        guard !candidates.isEmpty else {
            return nil
        }

        let stagingDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent("grvm-local-crash-\(UUID().uuidString)", isDirectory: true)
        do {
            try FileManager.default.createDirectory(
                at: stagingDirectory,
                withIntermediateDirectories: false,
                attributes: nil
            )
        } catch {
            return nil
        }

        var copiedURLs: [URL] = []
        var totalBytes: Int64 = 0
        for candidate in candidates {
            if copiedURLs.count >= maximumFileCount {
                break
            }
            let fileSize = candidate.fileSize
            if fileSize > maximumTotalBytes - totalBytes {
                continue
            }

            let destinationURL = stagingDirectory.appendingPathComponent(
                "\(copiedURLs.count)-\(candidate.url.lastPathComponent)",
                isDirectory: false
            )
            do {
                try FileManager.default.copyItem(at: candidate.url, to: destinationURL)
                let copiedValues = try destinationURL.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
                guard copiedValues.isRegularFile == true,
                      let copiedFileSize = copiedValues.fileSize,
                      copiedFileSize >= 0,
                      Int64(copiedFileSize) <= maximumTotalBytes - totalBytes else {
                    let _ = try? FileManager.default.removeItem(at: destinationURL)
                    continue
                }
                copiedURLs.append(destinationURL)
                totalBytes += Int64(copiedFileSize)
            } catch {
                let _ = try? FileManager.default.removeItem(at: destinationURL)
            }
        }

        if copiedURLs.isEmpty {
            let _ = try? FileManager.default.removeItem(at: stagingDirectory)
            return nil
        }
        return GRVMLocalCrashExportBundle(
            urls: copiedURLs,
            fileCount: copiedURLs.count,
            totalBytes: totalBytes,
            directoryURL: stagingDirectory
        )
    }

    private func safeCandidate(path: String) -> GRVMLocalCrashLogCandidate? {
        let originalURL = URL(fileURLWithPath: path, isDirectory: false).standardizedFileURL
        guard let values = try? originalURL.resourceValues(forKeys: [.isSymbolicLinkKey]),
              values.isSymbolicLink == false else {
            return nil
        }

        let canonicalURL = originalURL.resolvingSymlinksInPath()
        let rootPath = self.canonicalRootURL.path
        let candidatePath = canonicalURL.path
        guard candidatePath == rootPath || candidatePath.hasPrefix(rootPath + "/") else {
            return nil
        }

        guard let canonicalValues = try? canonicalURL.resourceValues(forKeys: [
            .isRegularFileKey,
            .fileSizeKey,
            .contentModificationDateKey,
            .creationDateKey,
        ]),
        canonicalValues.isRegularFile == true,
        let fileSize = canonicalValues.fileSize,
        fileSize >= 0 else {
            return nil
        }

        return GRVMLocalCrashLogCandidate(
            url: canonicalURL,
            fileSize: Int64(fileSize),
            date: canonicalValues.contentModificationDate ?? canonicalValues.creationDate ?? Date.distantPast
        )
    }
}
