import Foundation

public protocol LocalMessageDeletionMarker: MessageAttribute {
}

@inline(__always)
public func isLocallyDeletedMessage(_ attributes: [MessageAttribute]) -> Bool {
    return attributes.contains(where: { $0 is LocalMessageDeletionMarker })
}
