# ec2m

`ec2m` is a terminal utility for viewing local machine metrics and native AWS EC2 / CloudWatch metrics on demand.

Repository:

`https://github.com/Danila-F/ec2m`

## Install

Install from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/Danila-F/ec2m/main/install-ec2m.sh | bash
```

Install to a custom prefix:

```bash
curl -fsSL https://raw.githubusercontent.com/Danila-F/ec2m/main/install-ec2m.sh | INSTALL_PREFIX=/opt/ec2m bash
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/Danila-F/ec2m/main/install-ec2m.sh | bash -s -- --uninstall
```

## What gets installed

- `ec2m`
- `ec2-metrics`
- bundled Python dependencies required by the utility

The installer checks for `python3` and `pip`, installs them if needed, then installs or updates the utility.

## Basic usage

Show the default dashboard:

```bash
ec2m
```

Show available metrics:

```bash
ec2m --list
```

Show live updating view:

```bash
ec2m --live
```

Show compact watch mode:

```bash
ec2m --watch
```

Show only selected metrics:

```bash
ec2m -m local:cpu -m local:memory -m AWS/EC2:CPUUtilization
```

Show JSON output:

```bash
ec2m --json
```

## Help and diagnostics

```bash
ec2m --help
ec2m --version
ec2m --release-info
ec2m --doctor
```

## AWS setup

The utility prints the built-in AWS setup guide:

```bash
ec2m --setup-aws
```

For the default on-demand mode, the EC2 instance only needs CloudWatch read permissions.

## Examples

```bash
ec2m
ec2m --live
ec2m --watch
ec2m -m local:disk -m AWS/EC2:CPUCreditBalance
ec2m -m AWS/EC2:NetworkIn:Sum:300 -m AWS/EC2:NetworkOut:Sum:300
```

## Verify install

After installation:

```bash
ec2m --version
ec2m --help
```
