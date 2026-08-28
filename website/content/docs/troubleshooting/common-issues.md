# Troubleshooting

## Port conflicts (5432/5433 already in use)

A native Postgres install on your host will block the container's port
binding.

```bash
brew services stop postgresql        # macOS
sudo systemctl stop postgresql       # Linux
```

## Mesh communication silence

```bash
docker exec -it nats_mesh nats stream info AI_MESSAGES
```

## Stale emotional state

Verify Neo4j TTL cache invalidation:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_regressions.py::test_state_hydration_avoids_stale_cache
```

## WSL2 disk bloat (Windows)

The virtual disk (`ext4.vhdx`) never shrinks automatically — empty the
Recycle Bin (WSL deletions land there first) and run `wsl --shutdown` to
let Windows reclaim the space.

## The vision agent won't start in Docker

It must run on the host on Windows and macOS — Docker Desktop's Linux VM
has no route to the host display or webcam. See the Vision Agent row in
[Architecture](/docs/concepts/architecture). On Linux the containerized
path does work: uncomment the `devices`/X11 entries for `vision_agent` in
`docker-compose.prod.yml` and run `docker compose --profile vision up
vision_agent`.

## Something else

Open a [Discussion](https://github.com/Aniket-a14/AI_friend/discussions) or
[an issue](https://github.com/Aniket-a14/AI_friend/issues/new/choose) — see
[SUPPORT.md](https://github.com/Aniket-a14/AI_friend/blob/main/SUPPORT.md)
on GitHub for the full routing.
