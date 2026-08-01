import UIKit
import SwiftUI
import UniformTypeIdentifiers

/// The only platform extension in v1, and the reason this client is native
/// (spec §2.3). It inherits the login from the app through the shared cookie
/// store in the App Group — no token plumbing, no second sign-in — and when
/// that login is gone or the network is, it leaves the capture in the App
/// Group queue for the app to flush.
final class ShareViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear

        Task {
            let draft = await extractDraft()
            let sheet = UIHostingController(
                rootView: ForwardSheet(
                    draft: draft,
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
    private func extractDraft() async -> ForwardDraft {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            return ForwardDraft()
        }
        var draft = ForwardDraft()
        for item in items {
            if let title = item.attributedContentText?.string, draft.text == nil {
                draft.text = title
            }
            for provider in item.attachments ?? [] {
                if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier),
                   let url = try? await provider.loadItem(
                       forTypeIdentifier: UTType.url.identifier
                   ) as? URL {
                    draft.url = url.absoluteString
                } else if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier),
                          let text = try? await provider.loadItem(
                              forTypeIdentifier: UTType.plainText.identifier
                          ) as? String {
                    draft.text = text
                }
            }
        }
        return draft
    }
}
