# Private shared deployment over SSH

This deployment is for one owner's trusted devices, not a multi-tenant public API. The client launches `ssh -T` as its stdio MCP subprocess. SSH authenticates the device. There is no public HTTP MCP endpoint; clients that accept only a remote URL need a separate future HTTP transport.

Install application releases read-only under `/opt/shilu-studio/releases/<commit>`, point `current` at the chosen release. Keep the database in `/var/lib/shilu-studio` (0700), profile in `/etc/shilu-studio/profile.md`. Run as a dedicated `shilu-content` user. Do not expose the review app through public nginx.

For each device generate a distinct SSH key, and authorize its public key with:

    restrict,command="/opt/shilu-studio/current/deploy/ssh/run-mcp" ssh-ed25519 ... device-name

The forced command ignores shell commands; no PTY, forwarding or arbitrary shell. Do not give the Agent your admin SSH key. Revoke a device by removing its public key from this dedicated user's authorized_keys.

MCP client:

    {"command":"ssh","args":["-T","-o","BatchMode=yes","-o","IdentitiesOnly=yes","-i","/private/device-key","shilu-content@YOUR_HOST"]}

Human review uses a separate administrator-authorized tunnel:

    ssh -N -L 127.0.0.1:8775:127.0.0.1:8775 YOUR_ADMIN_HOST

Open `http://127.0.0.1:8775`. MCP does not expose review/export methods. The workflow assumes one owner trusts all connected Agents with this content store; it does not isolate different users' data.

The supplied systemd units run the loopback review app, synchronize the deployed public source bundle every ten minutes, and back up SQLite daily. Source changes block stale curation export. Missing projection files skip sync; inspect timer/service state and MCP `public_sync.synced_at`. A failed sync must not be interpreted as current data. Backups are retained for seven days; keep an additional off-server backup and test restoration. Never overwrite the live database during an application upgrade.

Use `shilu.release` only after human review. Copy just the public article JSON to the site importer; keep the release manifest and reviewer data private. Filesystem output and the database export-attempt record are not a distributed transaction; re-read project revision after any failure.
