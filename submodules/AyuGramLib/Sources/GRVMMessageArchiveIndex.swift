import Postbox
import SwiftSignalKit

public struct GRVMMessageArchiveSnapshot: Equatable {
    public let deleted: Set<GRVMMessageKey>
    public let revised: Set<GRVMMessageKey>

    public init(deleted: Set<GRVMMessageKey>, revised: Set<GRVMMessageKey>) {
        self.deleted = deleted
        self.revised = revised
    }
}

public final class GRVMMessageArchiveIndex {
    private let state = Atomic<GRVMMessageArchiveSnapshot>(
        value: GRVMMessageArchiveSnapshot(deleted: [], revised: [])
    )

    public init() {
    }

    public func snapshot() -> GRVMMessageArchiveSnapshot {
        return self.state.with { $0 }
    }

    public func replace(_ snapshot: GRVMMessageArchiveSnapshot) {
        _ = self.state.swap(snapshot)
    }

    public func insertDeleted(_ keys: Set<GRVMMessageKey>) {
        _ = self.state.modify { current in
            var deleted = current.deleted
            deleted.formUnion(keys)
            return GRVMMessageArchiveSnapshot(deleted: deleted, revised: current.revised)
        }
    }

    public func insertRevised(_ key: GRVMMessageKey) {
        _ = self.state.modify { current in
            var revised = current.revised
            revised.insert(key)
            return GRVMMessageArchiveSnapshot(deleted: current.deleted, revised: revised)
        }
    }

    public func removeDeleted(_ keys: Set<GRVMMessageKey>) {
        _ = self.state.modify { current in
            return GRVMMessageArchiveSnapshot(
                deleted: current.deleted.subtracting(keys),
                revised: current.revised
            )
        }
    }

    public func removeRevised(_ keys: Set<GRVMMessageKey>) {
        _ = self.state.modify { current in
            return GRVMMessageArchiveSnapshot(
                deleted: current.deleted,
                revised: current.revised.subtracting(keys)
            )
        }
    }

}
