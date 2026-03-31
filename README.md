# ec2m

`ec2m` is a terminal utility for viewing local machine metrics and native AWS EC2 / CloudWatch metrics on demand.

## Repository layout

- `src/ec2m.py`: editable source code of the utility
- `install-ec2m.sh`: single-file installer intended for `curl | bash`
- `scripts/update_installer_payload.py`: rebuilds the embedded installer payload from `src/ec2m.py`
- `cloudwatch-agent.json`: optional example config for CloudWatch Agent

## Install

After publishing this repository to GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/USER/REPO/main/install-ec2m.sh | bash
```

Install to a custom prefix:

```bash
curl -fsSL https://raw.githubusercontent.com/USER/REPO/main/install-ec2m.sh | INSTALL_PREFIX=/opt/ec2m bash
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/USER/REPO/main/install-ec2m.sh | bash -s -- --uninstall
```

## Editing the utility

The editable source lives in:

```bash
src/ec2m.py
```

After changing it, refresh the installer payload:

```bash
python3 scripts/update_installer_payload.py
```

Or:

```bash
make refresh-installer
```

## Local development flow

```bash
python3 src/ec2m.py --help
python3 src/ec2m.py --version
python3 scripts/update_installer_payload.py
```

## AWS setup

The utility prints the built-in AWS setup guide:

```bash
ec2m --setup-aws
```

For the default on-demand mode, the EC2 instance only needs CloudWatch read permissions.

## Publish to GitHub

From this directory:

```bash
git init
git add .
git commit -m "Initial ec2m repository"
git branch -M main
git remote add origin git@github.com:USER/REPO.git
git push -u origin main
```

If you prefer HTTPS:

```bash
git remote add origin https://github.com/USER/REPO.git
git push -u origin main
```

## Recommended release workflow

1. Edit `src/ec2m.py`
2. Run `python3 scripts/update_installer_payload.py`
3. Commit the source and updated installer together
4. Tag the release

Example tagged install URL:

```bash
curl -fsSL https://raw.githubusercontent.com/USER/REPO/v2026.03.31/install-ec2m.sh | bash
```

## Smoke test

Run on any target machine:

```bash
curl -fsSL https://raw.githubusercontent.com/USER/REPO/main/install-ec2m.sh | bash
ec2m --version
ec2m --help
```
