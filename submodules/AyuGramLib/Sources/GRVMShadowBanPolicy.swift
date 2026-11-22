public enum GRVMShadowBanPolicy {
    public static func normalizedPeerIds(
        _ peerIds: [Int64],
        accountPeerId: Int64
    ) -> [Int64] {
        var seen = Set<Int64>()
        return peerIds.filter { peerId in
            return peerId != accountPeerId && seen.insert(peerId).inserted
        }
    }

    public static func updatedPeerIds(
        _ peerIds: [Int64],
        peerId: Int64,
        isBanned: Bool,
        accountPeerId: Int64
    ) -> [Int64] {
        var result = self.normalizedPeerIds(peerIds, accountPeerId: accountPeerId)
        guard peerId != accountPeerId else {
            return result
        }
        if isBanned {
            if !result.contains(peerId) {
                result.append(peerId)
            }
        } else {
            result.removeAll(where: { $0 == peerId })
        }
        return result
    }
}
