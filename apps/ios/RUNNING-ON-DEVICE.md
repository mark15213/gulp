# Running Gulp on your own iPhone

The simulator shares the Mac's network and its filesystem, so it needs none of
this. A phone shares neither. Three things stand between a green build and an
app on your home screen — one of them is signing, which only you can do, and
two are in the code and already handled.

Everything here is **development only**. See [What must not ship](#what-must-not-ship).

---

## 1. Signing — the part nobody can do for you

The project ships with no `DEVELOPMENT_TEAM`, because signing identities belong
to a person, not to a repo.

1. **Xcode → Settings → Accounts → +** — add your Apple ID. A free one works.
2. `just ios`, then select the **Gulp** target → *Signing & Capabilities* →
   **Team**.
3. Do it again for the **GulpShare** target. An app extension is signed
   separately; forgetting it is the most common reason a device build fails
   after the app itself starts working.
4. On the phone: **Settings → Privacy & Security → Developer Mode → on.** iOS
   asks for a restart. This is required from iOS 16 onward.
5. Plug the phone in, pick it in Xcode's destination menu, ⌘R.

### Two things a free Apple ID costs you

**Profiles expire after 7 days.** The app stops launching and shows no useful
reason. Re-run from Xcode and it works again. A paid membership ($99/yr) gives
a year.

**App Groups may be refused.** `group.app.gulp.shared` is not decoration — it
is the entire mechanism by which the share extension inherits your login
(`spec §7.2`). If *Signing & Capabilities* shows it in red, you have two
options:

- Pay for a developer account, and everything works.
- Remove the App Group capability from both targets. The app itself is
  unaffected — it signs in and runs normally — but the share extension will
  get a `401`, because `HTTPCookieStorage.sharedCookieStorage(forGroup‑
  ContainerIdentifier:)` silently falls back to a per-process store when the
  group is unavailable. Forwarding from Safari would then queue locally into a
  container the app cannot read.

Xcode tells you which case you are in immediately. Do not guess.

---

## 2. Point the app at your Mac

`127.0.0.1` on a phone is the phone. The app has to be told your Mac's LAN
address instead.

Find it:

```sh
ipconfig getifaddr en0        # e.g. 192.168.1.49
```

In Xcode: **Product → Scheme → Edit Scheme → Run → Arguments →
Arguments Passed On Launch**:

```
-GulpBaseURL   http://192.168.1.49:8000
```

You only have to do this once. A launch argument normally lands in the volatile
argument domain and survives exactly the launch Xcode performs — tap the app on
the home screen afterwards and it would fall back to loopback with nothing
behind it. `GulpEnvironment.baseURL` promotes the value into the persistent
domain the first time it sees it, so it sticks across relaunches.

It does **not** stick across a network change. A new wifi means a new address
and a new pass through this step.

---

## 3. Run the backend where the phone can see it

`just api` binds loopback, which the phone cannot reach. Bind it to the LAN
instead:

```sh
just up                  # Postgres, Redis
just api 0.0.0.0         # the API, reachable from the phone
just worker              # in another window — packs and feeds need it
```

Loopback stays the default on purpose: `0.0.0.0` puts a dev server with dev
credentials on whatever network you happen to be on. Use it deliberately, on a
network you trust.

The phone and the Mac must be on the same wifi, and the Mac's firewall must
allow incoming connections for the Python process.

Check from the Mac before you blame the app:

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.1.49:8000/health   # 200
```

App Transport Security would normally block plain HTTP to that address. Both
targets set `NSAllowsLocalNetworking`, which permits local addresses as a class
— they cannot be listed individually because the address changes with the
network.

---

## 4. Check it worked

Sign in with your account. If Today loads a due count, the whole chain is up:
signing, the address, ATS, the API, the cookie.

Then the one thing the simulator has never proven — **forward from Safari.**
Share any page → Gulp. If it lands in your inbox, the extension is inheriting
the login through the App Group, which no automated test in this repo has been
able to demonstrate.

---

## When it does not work

| Symptom | Cause |
|---|---|
| `Unable to install` / `no profile` | No Team on one of the two targets — check **GulpShare**, not just Gulp |
| App installs, then refuses to open days later | Free-account profile expired after 7 days. Re-run from Xcode |
| `Untrusted Developer` | **Settings → General → VPN & Device Management** → trust your certificate |
| Everything loads on the simulator, nothing on the phone | The scheme argument is missing, or the API is still on loopback — `just api 0.0.0.0` |
| Sign-in spins, then "Can't reach Gulp" | Wrong LAN address (it changes with the network), different wifi, or the Mac's firewall |
| Sharing from Safari says "Sign in to Gulp on your phone first" | The App Group is not active on the extension — see §1 |
| Packs stay `NEEDS ATTENTION` | Unrelated to the device: no LLM key on the account. Add one at `/settings/ai` on web |

---

## What must not ship

Three things here exist only so a phone can talk to a laptop, and every one of
them is a hole in a shipped app:

- `NSAllowsLocalNetworking` and the `localhost` / `127.0.0.1` ATS exceptions in
  both `Info.plist` files.
- The `-GulpBaseURL` override, which now **persists** — a stored address is
  exactly the kind of thing that survives longer than the person who set it.
- `just api 0.0.0.0`.

A real build points at a real host over HTTPS and needs none of them. Strip
them in the same commit that introduces a deployment target, not later.
