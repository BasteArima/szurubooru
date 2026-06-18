# Deploying your fork via GHCR + Portainer

This describes how to run **your modified** szurubooru from images built by
GitHub Actions and published to the GitHub Container Registry (GHCR), then
deployed/redeployed from Portainer — no SSH needed for routine updates.

You run **two independent stacks** (e.g. `szuru-nsfw` and `szuru-sfw`). They use
the **same images** and differ only by env vars, config file, data dirs and
port — exactly like your current setup.

---

## 1. Push your fork to GitHub

The images are built from *your* repository, so it must live on GitHub:

```bash
# from your local clone that contains these changes
git remote add fork git@github.com:<YOU>/szurubooru.git   # or use the existing origin
git push fork master
```

On every push to `master`, the workflow `.github/workflows/build-ghcr.yml`
builds and pushes:

- `ghcr.io/<you>/szurubooru-server:latest`
- `ghcr.io/<you>/szurubooru-client:latest`

(`<you>` is your GitHub owner name, lowercased.)

Watch the run under the repo's **Actions** tab. First build takes a few minutes;
later builds are faster thanks to caching.

## 2. Make the packages public (one-time)

GHCR packages start **private**. After the first successful build:

1. Open `https://github.com/users/<you>/packages` (or the repo's *Packages*).
2. Open `szurubooru-server` → **Package settings** → **Change visibility** →
   **Public**. Repeat for `szurubooru-client`.

Public means Portainer can pull without any registry credentials.

> If you'd rather keep them private, add a GHCR registry (username + a PAT with
> `read:packages`) under Portainer → *Registries*, and skip this step.

## 3. Prepare per-instance config on the host

Each instance needs its own `config.yaml` on the host (bind-mounted read-only).
Put it next to that instance's data, e.g.:

```
/srv/.../szurubooru/config.yaml        # NSFW instance
/srv/.../szurubooru_sfw/config.yaml    # SFW instance
```

> ⚠️ **Reuse your CURRENT `secret` and DB credentials.** `secret` salts password
> hashes and on-disk filenames — if you change it, existing users can't log in
> and existing media paths break. Copy the value from your existing
> `./server/config.yaml`. Likewise keep `POSTGRES_USER`/`POSTGRES_PASSWORD`
> identical so the same database is used. No DB migration is needed for these
> changes (no schema changed).

Minimal **NSFW** `config.yaml` (registered users see unsafe, guests don't —
this is already the default from `config.yaml.dist`, shown here for clarity):

```yaml
name: My booru
secret: <KEEP-YOUR-EXISTING-SECRET>
domain: https://booru.example.com

privileges:
    'posts:view:unsafe': regular   # guests: no unsafe; registered: unsafe OK
```

Minimal **SFW** `config.yaml` (nobody ever sees unsafe media):

```yaml
name: My booru (SFW)
secret: <KEEP-YOUR-EXISTING-SFW-SECRET>
domain: https://sfw.example.com

privileges:
    'posts:view:unsafe': nobody    # unsafe hidden from everyone, everywhere
```

`posts:view:sketchy` works the same way for sketchy-rated media (default
`anonymous`, i.e. everyone). Set it to e.g. `regular` to hide sketchy from
guests, or `nobody` to hide it from everyone.

Everything you don't override is inherited from the baked-in `config.yaml.dist`.

## 4. Create the stacks in Portainer

In Portainer → **Stacks** → **Add stack** → *Web editor*, paste the contents of
[`docker-compose.ghcr.yml`](../docker-compose.ghcr.yml). Then fill the stack's
**Environment variables** (Portainer's env UI replaces your old `.env`):

**NSFW stack** (`szuru-nsfw`):

| Variable          | Value |
|-------------------|-------|
| `OWNER`           | your lowercased GitHub name |
| `POSTGRES_USER`   | `szuru` |
| `POSTGRES_PASSWORD` | *(your existing password)* |
| `THREADS`         | `4` |
| `BASE_URL`        | `/` |
| `PORT`            | `9398` |
| `MOUNT_DATA`      | `/srv/.../szurubooru/data` |
| `MOUNT_SQL`       | `/srv/.../szurubooru/sql` |
| `MOUNT_CONFIG`    | `/srv/.../szurubooru/config.yaml` |

**SFW stack** (`szuru-sfw`): same shape with the SFW values
(`POSTGRES_USER=szurusfw`, `PORT=9399`, the `_sfw` paths, etc.).

Deploy the stack. First deploy pulls the images from GHCR.

## 5. Redeploying after a code change

1. Commit + push to `master` → Actions rebuilds `:latest`.
2. Wait for the green check in **Actions**.
3. In Portainer open the stack → **Update the stack** and enable
   **Re-pull image and redeploy** (or use the *Recreate* / *Pull and redeploy*
   button on each service). Portainer pulls the new `:latest` and recreates the
   containers. Your data and DB volumes are untouched.

Do this for both stacks when you want both updated.

---

## Notes

- **First user = administrator.** On a fresh instance the first registered
  account becomes admin automatically. To promote someone later, an admin edits
  that user's *rank* on their profile edit page.
- **Dark theme** is now the default for new visitors. Anyone who previously
  saved settings keeps their prior choice (it lives in their browser).
- **Custom MIME types:** the old setups mounted `mime.py`. It's baked into the
  image now, so the mount is gone. If you need custom MIME handling, edit
  `server/szurubooru/func/mime.py` in the repo and rebuild, or bind-mount your
  own copy via an absolute host path.
