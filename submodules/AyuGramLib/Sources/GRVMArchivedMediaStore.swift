import CryptoUtils
import Foundation
import Postbox
import SwiftSignalKit

private func grvmResourceFilename(_ id: MediaResourceId) -> String {
    let data = Data(id.stringRepresentation.utf8)
    let digest: Data = data.withUnsafeBytes { bytes in
        CryptoSHA256(bytes.baseAddress!, Int32(data.count))
    }
    return digest.map { String(format: "%02x", $0) }.joined()
}

public final class GRVMArchivedMediaStore {
    private let rootURL: URL
    private let fileManager: FileManager
    private let queue = Queue(name: "GRVMArchivedMediaStore", qos: .utility)

    public init(rootURL: URL, fileManager: FileManager = .default) {
        self.rootURL = rootURL
        self.fileManager = fileManager
    }

    public func plannedRecord(accountId: Int64, resource: GRVMMediaResourceReference) -> GRVMArchivedMedia {
        let relativePath = self.resourceLocation(accountId: accountId, id: resource.id).relativePath
        return GRVMArchivedMedia(
            accountId: accountId,
            resourceId: resource.id.stringRepresentation,
            relativePath: relativePath,
            byteCount: 0,
            kind: resource.kind,
            copyState: .copying
        )
    }

    public func archive(
        _ record: GRVMArchivedMedia,
        resource: GRVMMediaResourceReference,
        mediaBox: MediaBox
    ) -> Signal<GRVMArchivedMedia, NoError> {
        return Signal { subscriber in
            self.queue.async {
                let location = self.resourceLocation(accountId: record.accountId, id: resource.id)
                guard let sourcePath = mediaBox.completedResourcePath(id: resource.id),
                      let byteCount = self.fileSize(atPath: sourcePath) else {
                    subscriber.putNext(self.terminalRecord(
                        record,
                        resource: resource,
                        relativePath: location.relativePath,
                        byteCount: 0,
                        copyState: .unavailable
                    ))
                    subscriber.putCompletion()
                    return
                }

                if self.fileSize(at: location.url) == byteCount {
                    subscriber.putNext(self.terminalRecord(
                        record,
                        resource: resource,
                        relativePath: location.relativePath,
                        byteCount: byteCount,
                        copyState: .complete
                    ))
                    subscriber.putCompletion()
                    return
                }

                let temporaryURL = location.url.appendingPathExtension("tmp")
                let complete = self.copyAtomically(
                    from: URL(fileURLWithPath: sourcePath),
                    to: location.url,
                    temporaryURL: temporaryURL,
                    expectedByteCount: byteCount
                )
                subscriber.putNext(self.terminalRecord(
                    record,
                    resource: resource,
                    relativePath: location.relativePath,
                    byteCount: complete ? byteCount : 0,
                    copyState: complete ? .complete : .unavailable
                ))
                subscriber.putCompletion()
            }
            return EmptyDisposable
        }
    }

    public func restore(_ record: GRVMArchivedMedia, to mediaBox: MediaBox) -> Signal<Bool, NoError> {
        guard record.copyState == .complete,
              let archiveURL = self.archiveURL(relativePath: record.relativePath) else {
            return .single(false)
        }
        return mediaBox.restoreResourceData(MediaResourceId(record.resourceId), fromPath: archiveURL.path)
    }

    public func remove(_ records: [GRVMArchivedMedia]) {
        self.queue.async {
            for record in records {
                guard let url = self.archiveURL(relativePath: record.relativePath) else {
                    continue
                }
                try? self.fileManager.removeItem(at: url)
            }
        }
    }

    private func resourceLocation(accountId: Int64, id: MediaResourceId) -> (relativePath: String, url: URL) {
        let filename = grvmResourceFilename(id)
        let prefix = String(filename.prefix(2))
        let relativePath = [String(accountId), "blobs", prefix, filename].joined(separator: "/")
        let url = self.rootURL
            .appendingPathComponent(String(accountId), isDirectory: true)
            .appendingPathComponent("blobs")
            .appendingPathComponent(prefix, isDirectory: true)
            .appendingPathComponent(filename, isDirectory: false)
        return (relativePath, url)
    }

    private func copyAtomically(
        from sourceURL: URL,
        to destinationURL: URL,
        temporaryURL: URL,
        expectedByteCount: Int64
    ) -> Bool {
        do {
            let parentURL = destinationURL.deletingLastPathComponent()
            try self.fileManager.createDirectory(
                at: parentURL,
                withIntermediateDirectories: true,
                attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication]
            )
            var resourceValues = URLResourceValues()
            resourceValues.isExcludedFromBackup = true
            var mutableParentURL = parentURL
            try mutableParentURL.setResourceValues(resourceValues)

            try? self.fileManager.removeItem(at: temporaryURL)
            do {
                try self.fileManager.linkItem(at: sourceURL, to: temporaryURL)
            } catch {
                try self.fileManager.copyItem(at: sourceURL, to: temporaryURL)
            }
            guard self.fileSize(at: temporaryURL) == expectedByteCount else {
                try? self.fileManager.removeItem(at: temporaryURL)
                return false
            }

            if self.fileManager.fileExists(atPath: destinationURL.path) {
                _ = try self.fileManager.replaceItemAt(destinationURL, withItemAt: temporaryURL)
            } else {
                try self.fileManager.moveItem(at: temporaryURL, to: destinationURL)
            }
            return self.fileSize(at: destinationURL) == expectedByteCount
        } catch {
            try? self.fileManager.removeItem(at: temporaryURL)
            return false
        }
    }

    private func archiveURL(relativePath: String) -> URL? {
        guard !relativePath.isEmpty,
              !relativePath.hasPrefix("/"),
              !relativePath.hasPrefix("\\"),
              !relativePath.split(separator: "/").contains("..") else {
            return nil
        }
        return self.rootURL.appendingPathComponent(relativePath, isDirectory: false)
    }

    private func fileSize(at url: URL) -> Int64? {
        return self.fileSize(atPath: url.path)
    }

    private func fileSize(atPath path: String) -> Int64? {
        guard let size = try? self.fileManager.attributesOfItem(atPath: path)[.size] as? NSNumber else {
            return nil
        }
        return size.int64Value
    }

    private func terminalRecord(
        _ record: GRVMArchivedMedia,
        resource: GRVMMediaResourceReference,
        relativePath: String,
        byteCount: Int64,
        copyState: GRVMArchivedMedia.CopyState
    ) -> GRVMArchivedMedia {
        return GRVMArchivedMedia(
            accountId: record.accountId,
            resourceId: resource.id.stringRepresentation,
            relativePath: relativePath,
            byteCount: byteCount,
            kind: resource.kind,
            copyState: copyState
        )
    }
}
