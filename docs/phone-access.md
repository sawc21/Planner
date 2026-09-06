# Private iPhone access with Tailscale

Tailscale Serve makes the localhost-only Semester Ops server available to devices in the same
private tailnet. It works when the iPhone is using cellular data or another Wi-Fi network. Do not
use Tailscale Funnel; Funnel would make the site public.

## 1. Join both devices to one tailnet

1. Install the current Tailscale client on the Windows computer and sign in.
2. Install Tailscale from the iOS App Store, approve its VPN configuration, and sign in with the
   same account.
3. Leave Tailscale connected on both devices.

Official installation guides:

- https://tailscale.com/docs/install/windows
- https://tailscale.com/docs/install/ios

## 2. Publish the local port privately

Start Semester Ops normally on the computer. In another PowerShell window, run:

```powershell
tailscale serve --bg http://127.0.0.1:8000
tailscale serve status
```

Serve prints a private URL similar to:

```text
https://computer-name.tailnet-name.ts.net
```

The first Serve command may open a Tailscale consent page to enable HTTPS certificates.

## 3. Trust that exact private origin

Put the exact URL printed by Tailscale in `.env`:

```dotenv
SEMOPS_HOST=127.0.0.1
SEMOPS_BASE_URL=https://computer-name.tailnet-name.ts.net
SEMOPS_SECRET_KEY=replace-with-a-long-random-local-secret
```

Do not add a wildcard and do not change `SEMOPS_HOST` to `0.0.0.0`. Restart Semester Ops after
editing `.env`. The configured HTTPS origin is added to the exact host allowlist and session
cookies are marked Secure. Once this is enabled, use the Tailscale HTTPS URL on the computer too;
the plain `http://127.0.0.1:8000` address cannot send the Secure session cookie.

## 4. Use it away from home

Open the printed HTTPS URL in Safari while Tailscale is connected. The phone may be on cellular or
gym Wi-Fi. You can then use **Share > Add to Home Screen** for an app-like icon.

The Windows computer must stay powered on, awake, connected to Tailscale, and running Semester
Ops. The `--bg` flag preserves the Serve proxy across Tailscale restarts, but it does not start the
Python application.

Access is controlled by the tailnet. Anyone allowed to reach this computer through the tailnet can
operate Semester Ops, so keep the tailnet private and restrict its access rules. To remove the
proxy configuration, run:

```powershell
tailscale serve reset
```

Tailscale Serve reference: https://tailscale.com/docs/features/tailscale-serve
