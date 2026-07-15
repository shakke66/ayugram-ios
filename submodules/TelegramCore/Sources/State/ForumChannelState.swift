import Foundation
import Postbox

enum InternalAccountState {
    static func addMessages(transaction: Transaction, messages: [StoreMessage], location: AddMessagesLocation) -> [Int64 : MessageId] {
        return transaction.addMessages(messages, location: location)
    }
    
    static func invalidateChannelState(peerId: PeerId) {
        
    }
}
