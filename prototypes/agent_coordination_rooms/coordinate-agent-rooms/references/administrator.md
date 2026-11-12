# Administrator runbook for a private team room

Use this runbook when the project authorizes a team pilot on an internal Linux
host or a dedicated VPS. Confirm the deployment target, approved DNS name,
ingress scope, data owner and backup location from project infrastructure rules.
Use a separate host when the pilot must be isolated from production workloads.
Use the project's normal change and rollback workflow.

## Components and network

One Python process runs `room_service.py` for one room. It serves the HTTPS
room protocol through a reverse proxy and stores the journal, memberships and
access-secret hashes in one local SQLite database. Desktop adapters run on
participants' PCs and poll the room over HTTPS. This pilot uses one writer
service instance with local storage. Leave the database off shared network
filesystems.

| Port | Purpose | Access |
| --- | --- | --- |
| TCP 443 | HTTPS reverse proxy | Approved team network, VPN or Internet if required |
| TCP 80 | Optional redirect or HTTP-01 certificate validation | Open only if the certificate or redirect setup needs it |
| TCP 8766 | Python upstream | Loopback `127.0.0.1` on the server |
| TCP 22 | Administration, if the host uses SSH | Infrastructure access path, VPN or administrator allowlist |

SQLite has no network port. Desktop clients use outbound HTTPS and require no
inbound port for invitations. For an Internet-reachable pilot, point DNS at the
proxy and terminate TLS there with a certificate trusted by clients. Keep the
Python listener on loopback. The prototype uses Python's
[`http.server`](https://docs.python.org/3/library/http.server.html) as a pilot
upstream.

## Install on the host

1. Deploy the reviewed revision of `coordinate-agent-rooms` under
   `/opt/kolabse-room`. Provide Python 3.11 or later and SQLite JSON functions.
2. Create a dedicated system user named `agent-room`. Keep the code readable
   and non-writable by that user. Create the private state directory and
   initialize a fresh room database.
3. Install the service unit and enable it after verifying the proxy configuration.

```sh
sudo install -d -o agent-room -g agent-room -m 0700 /var/lib/kolabse-room
sudo -u agent-room /usr/bin/python3 /opt/kolabse-room/scripts/room.py \
  --db /var/lib/kolabse-room/room.sqlite init --project pilot
```

Example `/etc/systemd/system/kolabse-room.service`:

```ini
[Unit]
Description=Kolabse agent coordination room pilot
After=network.target

[Service]
Type=simple
User=agent-room
Group=agent-room
WorkingDirectory=/opt/kolabse-room
StateDirectory=kolabse-room
StateDirectoryMode=0700
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=yes
ProtectSystem=strict
ExecStart=/usr/bin/python3 /opt/kolabse-room/scripts/room_service.py --db /var/lib/kolabse-room/room.sqlite serve --bind 127.0.0.1 --port 8766 --invite-only
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

If the project uses containers or another supervisor, preserve the same
unprivileged user, persistent local volume, loopback or isolated upstream
network, and restart behavior.

## Configure HTTPS ingress

Use the project's existing reverse proxy and certificate provisioning. This
NGINX example shows a pilot configuration inside the `http` context. Replace
the hostname and certificate paths with the approved values. Tune limits for
the team's polling rate and any shared egress addresses.

```nginx
limit_req_zone $binary_remote_addr zone=room_requests:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=room_signin:10m rate=10r/m;
limit_conn_zone $binary_remote_addr zone=room_connections:10m;
limit_conn_zone $server_name zone=room_total_connections:1m;
log_format room_access '$remote_addr $request_method $uri $status';

server {
    listen 443 ssl;
    server_name room.example.net;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    access_log /var/log/nginx/kolabse-room-access.log room_access;
    client_max_body_size 16k;
    client_header_timeout 10s;
    client_body_timeout 10s;
    limit_conn room_connections 10;
    limit_conn room_total_connections 64;
    limit_req_status 429;

    location ^~ /v1/team/ {
        limit_req zone=room_signin burst=5 nodelay;
        proxy_pass http://127.0.0.1:8766;
        proxy_connect_timeout 5s;
        proxy_read_timeout 15s;
    }

    location / {
        limit_req zone=room_requests burst=20 nodelay;
        proxy_pass http://127.0.0.1:8766;
        proxy_connect_timeout 5s;
        proxy_read_timeout 15s;
    }
}
```

If a load balancer sits in front of NGINX, configure client IP trust only for
that load balancer. Keep Authorization headers and request bodies out of
proxy logs. See the
[NGINX rate limit](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
and [proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
references.

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now kolabse-room
curl --fail --silent --show-error http://127.0.0.1:8766/health
sudo nginx -t
sudo systemctl reload nginx
curl --fail --silent --show-error https://room.example.net/health
```

## Add a participant and verify from a second workstation

Grant only approved projects. Generate the invitation from the server as the
service account and pass only its value directly to the intended participant.
See [participant setup](shared-room.md#team-access-with-one-time-invitations)
for the client commands.

```sh
sudo -u agent-room /usr/bin/python3 /opt/kolabse-room/scripts/room.py \
  --db /var/lib/kolabse-room/room.sqlite grant colleague --project pilot
sudo -u agent-room /usr/bin/python3 /opt/kolabse-room/scripts/room_service.py \
  --db /var/lib/kolabse-room/room.sqlite issue-invite colleague
```

From outside the host, verify that 443 is reachable with valid TLS and 8766 is
unreachable. Sign in using the invitation, post an addressed synthetic
question, reconnect and read it by cursor, then verify the reply in the same
thread. Revoke a test participant and verify that both history access and
credential renewal fail. Record the deployed revision and acceptance results
without including tokens, credentials or invitation values.

## Back up and recover

Schedule a [SQLite online backup](https://www.sqlite.org/backup.html) using the
project's encrypted, access-controlled backup storage. The backup contains
room history and access-control data. Use the SQLite `.backup` command or
Python's SQLite backup API for a running room. Record retention and test
restoration into an isolated instance.

For rollback, stop the service, keep the current database as a separate
recovery copy, and restore the reviewed code and a compatible backup as
required. A backup may restore previously revoked membership or still-valid
credentials. Review and reapply revocations or invalidate affected credentials
before making a restored room accessible. Verify health and access again after
restart.
