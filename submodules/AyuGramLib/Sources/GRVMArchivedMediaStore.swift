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

public struct GRVMMediaRemovalResult: Equatable {
    public let removed: [GRVMArchivedMedia]
    public let failed: [GRVMArchivedMedia]
}

private struct GRVMMediaRecordKey: Hashable {
    let accountId: Int64
    let resourceId: String
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
                subscriber.putNext(self.archiveRecord(record, resource: resource, mediaBox: mediaBox))
                subscriber.putCompletion()
            }
            return EmptyDisposable
        }
    }

    public func restore(_ record: GRVMArchivedMedia, to mediaBox: MediaBox) -> Signal<Bool, NoError> {
        guard record.copyState == .complete,
              let archiveURL = self.archiveURL(record: record) else {
            return .single(false)
        }
        return mediaBox.restoreResourceData(MediaResourceId(record.resourceId), fromPath: archiveURL.path)
    }

    public func removeArchivedFiles(_ records: [GRVMArchivedMedia]) -> GRVMMediaRemovalResult {
        var removed: [GRVMArchivedMedia] = []
        var failed: [GRVMArchivedMedia] = []
        self.queue.sync {
            var seen = Set<GRVMMediaRecordKey>()
            for record in records {
                let key = GRVMMediaRecordKey(accountId: record.accountId, resourceId: record.resourceId)
                guard seen.insert(key).inserted else {
                    continue
                }
                guard !record.relativePath.isEmpty else {
                    removed.append(record)
                    continue
                }
                guard let url = self.archiveURL(record: record) else {
                    failed.append(record)
                    continue
                }
                let removedFinal = self.removeIfPresent(url)
                let removedTemporary = self.removeIfPresent(url.appendingPathExtension("tmp"))
                if removedFinal && removedTemporary {
                    removed.append(record)
                } else {
                    failed.append(record)
                }
            }
        }
        return GRVMMediaRemovalResult(removed: removed, failed: failed)
    }

    public func remove(_ records: [GRVMArchivedMedia], completion: @escaping () -> Void = {}) {
        self.queue.async {
            _ = self.removeArchivedFiles(records)
            completion()
        }
    }

    public func reconcile(
        accountId: Int64,
        records: [GRVMArchivedMedia],
        mediaBox: MediaBox
    ) -> Signal<[GRVMArchivedMedia], NoError> {
        return Signal { subscriber in
            self.queue.async {
                let referencedRelativePaths = Set(records.compactMap { record -> String? in
                    guard record.accountId == accountId else {
                        return nil
                    }
                    if record.copyState == .copying {
                        return self.resourceLocation(
                            accountId: record.accountId,
                            id: MediaResourceId(record.resourceId)
                        ).relativePath
                    }
                    guard record.relativePath.hasPrefix("\(accountId)/blobs/"),
                          self.archiveURL(record: record) != nil else {
                        return nil
                    }
                    return record.relativePath
                })
                let blobsURL = self.rootURL
                    .appendingPathComponent(String(accountId), isDirectory: true)
                    .appendingPathComponent("blobs", isDirectory: true)
                var cleanupFailed = false
                if let enumerator = self.fileManager.enumerator(
                    at: blobsURL,
                    includingPropertiesForKeys: [.isRegularFileKey],
                    options: []
                ) {
                    for case let fileURL as URL in enumerator {
                        guard (try? fileURL.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true else {
                            continue
                        }
                        if fileURL.pathExtension == "tmp" {
                            if !self.removeIfPresent(fileURL) {
                                cleanupFailed = true
                                break
                            }
                            continue
                        }
                        let prefix = self.rootURL.path + "/"
                        guard fileURL.path.hasPrefix(prefix) else {
                            continue
                        }
                        let relativePath = String(fileURL.path.dropFirst(prefix.count))
                        if !referencedRelativePaths.contains(relativePath) {
                            if !self.removeIfPresent(fileURL) {
                                cleanupFailed = true
                                break
                            }
                        }
                    }
                }
                guard !cleanupFailed else {
                    subscriber.putCompletion()
                    return
                }

                var updates: [GRVMArchivedMedia] = []
                for record in records where record.accountId == accountId {
                    switch record.copyState {
                    case .copying:
                        let resource = GRVMMediaResourceReference(
                            id: MediaResourceId(record.resourceId),
                            kind: record.kind
                        )
                        let location = self.resourceLocation(accountId: record.accountId, id: resource.id)
                        if let byteCount = self.fileSize(at: location.url), byteCount > 0 {
                            updates.append(self.terminalRecord(
                                record,
                                resource: resource,
                                relativePath: location.relativePath,
                                byteCount: byteCount,
                                copyState: .complete
                            ))
                            continue
                        }

                        let temporaryURL = location.url.appendingPathExtension("tmp")
                        if mediaBox.completedResourcePath(id: resource.id) == nil {
                            guard self.removeIfPresent(temporaryURL) else {
                                subscriber.putCompletion()
                                return
                            }
                        }
                        let recovered = self.archiveRecord(record, resource: resource, mediaBox: mediaBox)
                        if recovered.copyState == .complete {
                            updates.append(recovered)
                        } else {
                            guard self.removeIfPresent(temporaryURL) else {
                                subscriber.putCompletion()
                                return
                            }
                            updates.append(self.terminalRecord(
                                record,
                                resource: resource,
                                relativePath: location.relativePath,
                                byteCount: 0,
                                copyState: .unavailable
                            ))
                        }
                    case .complete:
                        guard let url = self.archiveURL(record: record),
                              self.fileManager.fileExists(atPath: url.path) else {
                            updates.append(GRVMArchivedMedia(
                                accountId: record.accountId,
                                resourceId: record.resourceId,
                                relativePath: record.relativePath,
                                byteCount: record.byteCount,
                                kind: record.kind,
                                copyState: .missing
                            ))
                            continue
                        }
                    case .unavailable, .missing:
                        break
                    }
                }
                subscriber.putNext(updates)
                subscriber.putCompletion()
            }
            return EmptyDisposable
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

    private func archiveRecord(
        _ record: GRVMArchivedMedia,
        resource: GRVMMediaResourceReference,
        mediaBox: MediaBox
    ) -> GRVMArchivedMedia {
        let location = self.resourceLocation(accountId: record.accountId, id: resource.id)
        guard let sourcePath = mediaBox.completedResourcePath(id: resource.id),
              let byteCount = self.fileSize(atPath: sourcePath),
              byteCount > 0 else {
            return self.terminalRecord(
                record,
                resource: resource,
                relativePath: location.relativePath,
                byteCount: 0,
                copyState: .unavailable
            )
        }

        if self.fileSize(at: location.url) == byteCount {
            return self.terminalRecord(
                record,
                resource: resource,
                relativePath: location.relativePath,
                byteCount: byteCount,
                copyState: .complete
            )
        }

        let temporaryURL = location.url.appendingPathExtension("tmp")
        let complete = self.copyAtomically(
            from: URL(fileURLWithPath: sourcePath),
            to: location.url,
            temporaryURL: temporaryURL,
            expectedByteCount: byteCount
        )
        return self.terminalRecord(
            record,
            resource: resource,
            relativePath: location.relativePath,
            byteCount: complete ? byteCount : 0,
            copyState: complete ? .complete : .unavailable
        )
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

            guard self.removeIfPresent(temporaryURL) else {
                return false
            }
            do {
                try self.fileManager.linkItem(at: sourceURL, to: temporaryURL)
            } catch {
                try self.fileManager.copyItem(at: sourceURL, to: temporaryURL)
            }
            guard self.fileSize(at: temporaryURL) == expectedByteCount else {
                _ = self.removeIfPresent(temporaryURL)
                return false
            }

            if self.fileManager.fileExists(atPath: destinationURL.path) {
                _ = try self.fileManager.replaceItemAt(destinationURL, withItemAt: temporaryURL)
            } else {
                try self.fileManager.moveItem(at: temporaryURL, to: destinationURL)
            }
            return self.fileSize(at: destinationURL) == expectedByteCount
        } catch {
            _ = self.removeIfPresent(temporaryURL)
            return false
        }
    }

    private func removeIfPresent(_ url: URL) -> Bool {
        do {
            try self.fileManager.removeItem(at: url)
            return true
        } catch {
            let nsError = error as NSError
            return nsError.domain == NSCocoaErrorDomain && nsError.code == NSFileNoSuchFileError
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

    private func archiveURL(record: GRVMArchivedMedia) -> URL? {
        let expected = self.resourceLocation(
            accountId: record.accountId,
            id: MediaResourceId(record.resourceId)
        )
        guard record.relativePath.hasPrefix("\(record.accountId)/blobs/"),
              record.relativePath == expected.relativePath else {
            return nil
        }
        return self.archiveURL(relativePath: record.relativePath)
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
