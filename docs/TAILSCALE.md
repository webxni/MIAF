# Tailscale Private Access

MIAF supports private phone/remote access via [Tailscale Serve](https://tailscale.com/kb/1242/tailscale-serve).
Tailscale Serve shares MIAF only inside your private tailnet — **it is not Tailscale Funnel and does not expose anything to the public internet**.

## How it works

```
Phone (Tailscale)  ──tailnet──►  Host machine  ──localhost──►  Caddy :<HTTP_PORT>  ──►  MIAF
```

1. Tailscale Serve listens on the host at a `https://<hostname>.ts.net` URL.
2. It forwards requests to `http://127.0.0.1:<HTTP_PORT>` (Caddy), which reverse-proxies to the API and web containers.
3. Only devices authenticated in the same Tailscale account (tailnet) can reach that URL.

## Prerequisites

- Tailscale installed on the host machine running MIAF ([tailscale.com/download](https://tailscale.com/download)).
- Tailscale installed and signed in on every device that needs access (phone, second laptop, etc.).
- Both devices must be in the **same tailnet** (same Tailscale account).

## Setup — Quickstart

```bash
# 1. Install Tailscale on the host
curl -fsSL https://tailscale.com/install.sh | sh

# 2. Connect the host to your tailnet
sudo tailscale up

# 3. Start Serve (points at Caddy on the host HTTP port)
make tailscale-serve
# equivalent to: sudo tailscale serve --bg http://127.0.0.1:<HTTP_PORT>

# 4. Check the URL
make tailscale-serve-status
# Look for the https://*.ts.net line — open that on your phone
```

## Setup — From the UI

After creating your owner account, MIAF redirects to **Onboarding → Tailscale** where you can:

- See live binary availability, Tailscale IP, and hostname.
- Click **Start Tailscale Serve** to run the command from the API container (if the binary is mounted).
- Copy manual commands for host-side setup.

You can also reach this later at **Settings → Tailscale private access**.

## Host vs. container

MIAF runs in Docker. The Tailscale binary is normally installed on the **host**, not inside a container.

| Scenario | What to do |
|---|---|
| Binary on host only | Run `make tailscale-serve` on the host. The UI shows the copy-pasteable commands. |
| Binary mounted into `api` container | Set `TAILSCALE_BINARY_PATH` in `.env` to the mounted path; the UI **Start Serve** button will work. |
| Tailscale sidecar container | Not required; not supported by default. Use the host binary. |

To mount the host binary read-only into the API container, add to `compose.yaml`:

```yaml
services:
  api:
    volumes:
      - /usr/bin/tailscale:/usr/bin/tailscale:ro
```

Then set `TAILSCALE_BINARY_PATH=/usr/bin/tailscale` in `.env`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TAILSCALE_BINARY_PATH` | `/usr/bin/tailscale` | Path to the tailscale binary (checked first, then `$PATH`) |
| `TAILSCALE_COMMAND_TIMEOUT` | `10` | Seconds before a tailscale subprocess is killed |
| `TAILSCALE_ALLOWED_PORTS` | `80` | Comma-separated list of local ports allowed as Serve targets |

If your install uses a non-default `HTTP_PORT`, include it in `TAILSCALE_ALLOWED_PORTS`. The installer and `miaf setup` now do this automatically.

## Makefile helpers

```bash
make tailscale-status        # tailscale status --json | python3 -m json.tool
make tailscale-ip            # tailscale ip -4
make tailscale-serve         # sudo tailscale serve --bg http://127.0.0.1:<HTTP_PORT>
make tailscale-serve-status  # tailscale serve status
make tailscale-serve-reset   # sudo tailscale serve reset
```

## Security model

| Property | Detail |
|---|---|
| Traffic scope | Private tailnet only — no public internet exposure |
| Funnel | Never started by MIAF |
| Target allowlist | Only `localhost`/`127.0.0.1` targets are accepted; port must be in `TAILSCALE_ALLOWED_PORTS` |
| Command execution | `asyncio.create_subprocess_exec` with list args — no shell injection possible |
| Audit | Every check / serve-start / serve-reset action writes an audit log row |
| Auth gate | Only `owner` or `admin` users can trigger Tailscale actions via the API |

## Direct-IP access (no Serve)

If you don't want Serve, you can open MIAF directly via the Tailscale IP:

```bash
tailscale ip -4   # e.g. 100.64.0.5
```

Then on your phone, open `http://100.64.0.5:<HTTP_PORT>`. This works as long as:

- Caddy is listening on your configured `HTTP_PORT`.
- Your tailnet ACLs allow the connection (they do by default for new tailnets).

Serve is recommended because it gives you an `https://` URL with a stable hostname.

## Troubleshooting

**"tailscale binary not found"**  
Install Tailscale on the host or mount the binary into the container (see above).

**Start Serve returns an error**  
The API container runs as a non-root user. `tailscale serve` may need root or the `tailscaled` socket to be accessible. Run `sudo tailscale serve --bg http://127.0.0.1:80` on the host instead.

**Phone can't reach the URL**  
- Make sure both devices are signed into the same Tailscale account.
- Run `tailscale status` on the host and verify the phone appears in the peer list.
- Check that Tailscale Serve is running: `tailscale serve status`.

**Caddy is not listening on port 80**  
Check `make ps` — the `caddy` service must be running. Check `make logs` for errors.
