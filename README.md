# ec2m

[Русская версия README](./README.ru.md)

`ec2m` is a terminal utility for viewing local Linux metrics and native AWS EC2 / CloudWatch metrics directly from the terminal.

It is designed for on-demand use:

- no web console required
- no long-running background service required
- works well for EC2 burstable instances where CPU credit metrics matter

Source code for the utility is available in `src/ec2m.py`.

## Install

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

## What it can show

- local CPU, memory, disk and load
- native EC2 / CloudWatch metrics such as `CPUUtilization`, `CPUCreditBalance`, `CPUCreditUsage`, network and status checks
- live updating terminal views
- JSON output for scripting

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

## Requirements for AWS metrics

To read AWS metrics from inside an EC2 instance, the instance needs an IAM role with CloudWatch read permissions.

If AWS access is not configured, `ec2m` still works for local machine metrics.

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
ec2m --doctor
ec2m -m local:disk -m AWS/EC2:CPUCreditBalance
ec2m -m AWS/EC2:NetworkIn:Sum:300 -m AWS/EC2:NetworkOut:Sum:300
ec2m -m local:cpu -m local:memory -m AWS/EC2:CPUUtilization
ec2m --json
```

## Verify install

After installation:

```bash
ec2m --version
ec2m --help
```

## Versioning

Stable versions are intended to be published as git tags in the form `vYYYY.MM.DD`.

Example:

```bash
curl -fsSL https://raw.githubusercontent.com/Danila-F/ec2m/v2026.03.31/install-ec2m.sh | bash
```
