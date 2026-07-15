import Postbox
import SwiftSignalKit
import TelegramCore
import AyuGramLib

/// Account-scoped asynchronous entry points used by archive UI modules.
public enum AyuGramFeatures {
    public static var deletedMessages: ((PeerId, PeerId?, Int64?, String?) -> Signal<[GRVMArchivedMessage], NoError>)?
    public static var clearDeleted: ((PeerId, PeerId?, Int64?) -> Signal<[MessageId], NoError>)?
    public static var editHistory: ((PeerId, MessageId) -> Signal<[GRVMEditRevision], NoError>)?
}
