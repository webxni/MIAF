# Local development

## What runs in `docker compose up`

| Service     | Image / build                          | Internal port | Exposed on host |
|-------------|----------------------------------------|---------------|-----------------|
| caddy       | `caddy:2-alpine`                       | 80, 443       | `${HTTP_PORT}`, `${HTTPS_PORT}` |
| web         | `apps/web/Dockerfile` (target `dev`)   | 3000          | — (proxied via Caddy) |
| api         | `apps/api/Dockerfile` (target `dev`)   | 8000          | — (proxied via Caddy under `/api`) |
| worker      | `services/worker/Dockerfile`           | —             | — |
| scheduler   | `services/scheduler/Dockerfile`        | —             | — |
| postgres    | `pgvector/pgvector:pg16`               | 5432          | — (internal only) |
| redis       | `redis:7-alpine`                       | 6379          | — (internal only) |
| minio       | `minio/minio`                          | 9000 (S3), 9001 (console) | console on `127.0.0.1:9001` (dev only) |
| backup      | `infra/docker/backup/Dockerfile`       | —             | — |

All services share the user-defined bridge network `finclaw_internal`.

## Editing code

* Backend (`apps/api`, `services/worker`, `services/scheduler`) is bind-mounted into the container. The api uses `uvicorn --reload`, so a save round-trips in <1s.
* Frontend (`apps/web`) is bind-mounted into the container. Next.js dev server picks up changes automatically. `node_modules` and `.next` are kept in named volumes so they don't get clobbered by the host mount.

## Health checks

```bash
make smoke
# -> {"status":"ok"}
# -> {"status":"ok","checks":{"postgres":"ok","redis":"ok","minio":"ok"}}
```

The `/health/ready` probe verifies that pgvector is installed, redis answers PING, and the MinIO bucket exists (creating it on first call).

## Reset everything

```bash
make clean   # destructive — drops all volumes
make build
make up
```
