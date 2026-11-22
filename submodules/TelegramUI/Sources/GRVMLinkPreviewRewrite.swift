import Foundation

func grvmRewrittenLinkPreviewUrl(_ url: String) -> String {
    guard var components = URLComponents(string: url),
          let scheme = components.scheme?.lowercased(),
          scheme == "http" || scheme == "https",
          let host = components.host?.lowercased() else {
        return url
    }

    let previewHost: String
    switch host {
    case "twitter.com", "www.twitter.com", "x.com", "www.x.com":
        previewHost = "fixupx.com"
    case "tiktok.com", "www.tiktok.com":
        previewHost = "kktiktok.com"
    case "reddit.com", "www.reddit.com":
        previewHost = "vxreddit.com"
    case "instagram.com", "www.instagram.com":
        previewHost = "kkclip.com"
    case "pixiv.net", "www.pixiv.net":
        previewHost = "phixiv.net"
    default:
        guard host.hasSuffix(".tiktok.com") else {
            return url
        }
        let subdomain = String(host.dropLast(".tiktok.com".count))
        guard !subdomain.isEmpty else {
            return url
        }
        previewHost = "\(subdomain).kktiktok.com"
    }

    components.host = previewHost
    return components.string ?? url
}
