import UIKit
import SwiftUI
import UniformTypeIdentifiers

/// The only platform extension in v1, and the reason this client is native
/// (spec §2.3). It inherits the login from the app through the shared cookie
/// store in the App Group — no token plumbing, no second sign-in.
final class ShareViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear

        Task {
            let payload = await extractPayload()
            let sheet = UIHostingController(
                rootView: ForwardSheet(
                    payload: payload,
                    finish: { [weak self] in self?.finish() }
                )
            )
            sheet.view.backgroundColor = .clear
            addChild(sheet)
            sheet.view.frame = view.bounds
            sheet.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(sheet.view)
            sheet.didMove(toParent: self)
        }
    }

    private func finish() {
        extensionContext?.completeRequest(returningItems: nil)
    }

    /// Whatever the host app handed over: a URL if there is one, otherwise
    /// text. Anything unrecognised still forwards — an unsupported type is
    /// stored raw rather than refused (`01 §10.3`).
    private func extractPayload() async -> SharePayload {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            return SharePayload()
        }
        var payload = SharePayload()
        for item in items {
            if let title = item.attributedContentText?.string, payload.text == nil {
                payload.text = title
            }
            for provider in item.attachments ?? [] {
                if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier),
                   let url = try? await provider.loadItem(
                       forTypeIdentifier: UTType.url.identifier
                   ) as? URL {
                    payload.url = url.absoluteString
                } else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier),
                          let text = try? await provider.loadItem(
                              forTypeIdentifier: UTType.plainText.identifier
                          ) as? String {
                    payload.text = text
                }
            }
        }
        return payload
    }
}

struct SharePayload {
    var url: String?
    var text: String?

    var detectedTitle: String {
        if let text, !text.isEmpty, text.count < 120 { return text }
        if let url, let host = URL(string: url)?.host() { return host }
        return "Untitled"
    }

    var host: String? {
        guard let url else { return nil }
        return URL(string: url)?.host()
    }
}
