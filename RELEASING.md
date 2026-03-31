# Releasing ec2m

One-command release flow:

```bash
./scripts/release.sh
```

This uses today's UTC date and creates a tag like `v2026.03.31`.

To publish a specific version explicitly:

```bash
./scripts/release.sh 2026.04.01
```

Or:

```bash
./scripts/release.sh v2026.04.01
```

Dry-run without creating a tag:

```bash
./scripts/release.sh --dry-run
```

What the script checks before tagging:

- the git worktree is clean
- the current branch is `main`
- local `main` matches `origin/main`
- the requested tag does not already exist locally or on `origin`

What happens after the tag is pushed:

1. GitHub Actions runs the `Release` workflow
2. The workflow validates `src/ec2m.py`
3. The workflow verifies that `install-ec2m.sh` matches the generated payload
4. The workflow runs a smoke install/uninstall test
5. GitHub publishes a release for the tag
6. The release uploads `install-ec2m.sh` and `SHA256SUMS`
7. The release is marked as `Latest`

Useful install links after release:

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/latest/download/install-ec2m.sh | bash
```

```bash
curl -fsSL https://github.com/Danila-F/ec2m/releases/download/v2026.03.31/install-ec2m.sh | bash
```
