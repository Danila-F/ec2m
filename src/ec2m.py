#!/usr/bin/env python3
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

VERSION = "2026.03.31"
RELEASE_DATE = "2026-03-31"
RELEASE_CHANNEL = "stable"


COMMON_METRICS_BY_NAMESPACE = {
    "AWS/EC2": {
        "CPUUtilization": {"stat": "Average", "period": 60, "description": "CPU load percent"},
        "CPUCreditBalance": {"stat": "Maximum", "period": 300, "description": "Remaining CPU credits"},
        "CPUCreditUsage": {"stat": "Sum", "period": 300, "description": "Spent CPU credits"},
        "CPUSurplusCreditBalance": {
            "stat": "Maximum",
            "period": 300,
            "description": "Unlimited surplus credit debt",
        },
        "CPUSurplusCreditsCharged": {"stat": "Sum", "period": 300, "description": "Charged surplus credits"},
        "StatusCheckFailed": {"stat": "Maximum", "period": 60, "description": "Any EC2 status check failed"},
        "StatusCheckFailed_Instance": {
            "stat": "Maximum",
            "period": 60,
            "description": "Instance status check failed",
        },
        "StatusCheckFailed_System": {
            "stat": "Maximum",
            "period": 60,
            "description": "System status check failed",
        },
        "NetworkIn": {"stat": "Sum", "period": 300, "description": "Incoming bytes"},
        "NetworkOut": {"stat": "Sum", "period": 300, "description": "Outgoing bytes"},
        "NetworkPacketsIn": {"stat": "Sum", "period": 300, "description": "Incoming packets"},
        "NetworkPacketsOut": {"stat": "Sum", "period": 300, "description": "Outgoing packets"},
        "DiskReadBytes": {"stat": "Sum", "period": 300, "description": "Instance store bytes read"},
        "DiskWriteBytes": {"stat": "Sum", "period": 300, "description": "Instance store bytes written"},
        "DiskReadOps": {"stat": "Sum", "period": 300, "description": "Instance store read ops"},
        "DiskWriteOps": {"stat": "Sum", "period": 300, "description": "Instance store write ops"},
        "EBSReadBytes": {"stat": "Sum", "period": 300, "description": "EBS bytes read"},
        "EBSWriteBytes": {"stat": "Sum", "period": 300, "description": "EBS bytes written"},
        "EBSReadOps": {"stat": "Sum", "period": 300, "description": "EBS read ops"},
        "EBSWriteOps": {"stat": "Sum", "period": 300, "description": "EBS write ops"},
        "MetadataNoToken": {"stat": "Sum", "period": 300, "description": "IMDSv1 metadata calls"},
        "MetadataNoTokenRejected": {"stat": "Sum", "period": 300, "description": "Rejected IMDSv1 calls"},
    },
    "CWAgent": {
        "cpu_usage_active": {"stat": "Average", "period": 60, "description": "Agent CPU usage percent"},
        "mem_used_percent": {"stat": "Average", "period": 60, "description": "RAM usage percent"},
        "swap_used_percent": {"stat": "Average", "period": 60, "description": "Swap usage percent"},
        "disk_used_percent": {"stat": "Average", "period": 60, "description": "Root filesystem usage percent"},
        "disk_inodes_free": {"stat": "Average", "period": 60, "description": "Free inodes on root filesystem"},
        "net_bytes_recv": {"stat": "Sum", "period": 60, "description": "Received bytes"},
        "net_bytes_sent": {"stat": "Sum", "period": 60, "description": "Sent bytes"},
        "net_packets_recv": {"stat": "Sum", "period": 60, "description": "Received packets"},
        "net_packets_sent": {"stat": "Sum", "period": 60, "description": "Sent packets"},
    },
}

LOCAL_METRICS = {
    "cpu": "Current local CPU usage percent",
    "load": "Load average normalized to vCPU count",
    "memory": "RAM usage percent",
    "swap": "Swap usage percent",
    "disk": "Root filesystem usage percent",
}

DEFAULT_SPECS = [
    "local:cpu",
    "local:memory",
    "local:disk",
    "local:load",
    "AWS/EC2:CPUUtilization",
    "AWS/EC2:CPUCreditBalance",
    "AWS/EC2:CPUCreditUsage",
    "AWS/EC2:StatusCheckFailed",
    "AWS/EC2:NetworkIn",
    "AWS/EC2:NetworkOut",
]

BYTE_METRICS = {
    "NetworkIn",
    "NetworkOut",
    "DiskReadBytes",
    "DiskWriteBytes",
    "EBSReadBytes",
    "EBSWriteBytes",
    "net_bytes_recv",
    "net_bytes_sent",
}

COUNT_METRICS = {
    "NetworkPacketsIn",
    "NetworkPacketsOut",
    "DiskReadOps",
    "DiskWriteOps",
    "EBSReadOps",
    "EBSWriteOps",
    "MetadataNoToken",
    "MetadataNoTokenRejected",
    "net_packets_recv",
    "net_packets_sent",
}

STATUS_METRICS = {
    "StatusCheckFailed",
    "StatusCheckFailed_Instance",
    "StatusCheckFailed_System",
}

PERCENT_METRICS = {
    "cpu_usage_active",
    "mem_used_percent",
    "swap_used_percent",
    "disk_used_percent",
}

CPU_CREDIT_LIMITS = {
    "t2.nano": 72.0,
    "t2.micro": 144.0,
    "t2.small": 288.0,
    "t2.medium": 576.0,
    "t2.large": 864.0,
    "t2.xlarge": 1296.0,
    "t2.2xlarge": 1958.4,
    "t3.nano": 144.0,
    "t3.micro": 288.0,
    "t3.small": 576.0,
    "t3.medium": 576.0,
    "t3.large": 864.0,
    "t3.xlarge": 2304.0,
    "t3.2xlarge": 4608.0,
    "t3a.nano": 144.0,
    "t3a.micro": 288.0,
    "t3a.small": 576.0,
    "t3a.medium": 576.0,
    "t3a.large": 864.0,
    "t3a.xlarge": 2304.0,
    "t3a.2xlarge": 4608.0,
    "t4g.nano": 144.0,
    "t4g.micro": 288.0,
    "t4g.small": 576.0,
    "t4g.medium": 576.0,
    "t4g.large": 864.0,
    "t4g.xlarge": 2304.0,
    "t4g.2xlarge": 4608.0,
}

METADATA_TOKEN = None

HELP_EPILOG = """Examples:
  ec2m
  ec2m --watch
  ec2m --live
  ec2m -m local:cpu -m local:memory -m local:disk
  ec2m -m AWS/EC2:CPUUtilization -m AWS/EC2:CPUCreditBalance
  ec2m -m local:memory -m local:disk -m local:swap
  ec2m -m CWAgent:mem_used_percent -m CWAgent:disk_used_percent
  ec2m -m AWS/EC2:NetworkIn:Sum:300 -m AWS/EC2:NetworkOut:Sum:300
  ec2m --json
  ec2m --doctor
  ec2m --setup-aws
  ec2m --version
  ec2m --release-info

Metric syntax:
  local:<name>
  MetricName
  Namespace:MetricName
  MetricName:Stat:Period
  Namespace:MetricName:Stat:Period

Namespaces:
  local     Live values read directly from Linux on this machine.
  AWS/EC2   Native EC2 metrics already published by AWS.
  CWAgent   OS-level metrics published by Amazon CloudWatch Agent.

Notes:
  Without -m, ec2m shows local live metrics plus native AWS/EC2 metrics.
  CloudWatch values are near-real-time, not instantaneous.
  CWAgent metrics are optional and require a background CloudWatch Agent service.
"""


ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
}


def metadata(path: str) -> str:
    global METADATA_TOKEN
    if METADATA_TOKEN is None:
        token_request = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        )
        METADATA_TOKEN = urllib.request.urlopen(token_request, timeout=2).read().decode().strip()
    request = urllib.request.Request(
        "http://169.254.169.254" + path,
        headers={"X-aws-ec2-metadata-token": METADATA_TOKEN},
    )
    return urllib.request.urlopen(request, timeout=2).read().decode().strip()


def human_bytes(value: float) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(value)
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{value:.2f} B"


def human_count(value: float) -> str:
    thresholds = [(1_000_000_000, "G"), (1_000_000, "M"), (1_000, "K")]
    for threshold, suffix in thresholds:
        if abs(value) >= threshold:
            return f"{value / threshold:.2f} {suffix}"
    return f"{value:.2f}"


def colors_enabled() -> bool:
    real_stdout = getattr(sys, "__stdout__", sys.stdout)
    return real_stdout.isatty() and os.environ.get("NO_COLOR") is None


def paint(text: str, *styles: str) -> str:
    if not colors_enabled():
        return text
    prefix = "".join(ANSI[style] for style in styles)
    return f"{prefix}{text}{ANSI['reset']}"


def percent_bar(percent_value: float, width: int = 26) -> str:
    clamped = max(0.0, min(100.0, percent_value))
    filled = int(round((clamped / 100.0) * width))
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}]"


def percent_color(percent_value: float) -> str:
    if percent_value >= 85:
        return "red"
    if percent_value >= 60:
        return "yellow"
    return "green"


def short_timestamp(timestamp: str) -> str:
    if timestamp == "NO_TIMESTAMP":
        return timestamp
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except ValueError:
        return timestamp


def terminal_interactive() -> bool:
    return sys.stdout.isatty() and sys.stdin.isatty()


def enter_alt_screen() -> None:
    if terminal_interactive():
        print("\033[?1049h\033[?25l", end="", flush=True)


def leave_alt_screen() -> None:
    if terminal_interactive():
        print("\033[?25h\033[?1049l", end="", flush=True)


def redraw_frame() -> None:
    if terminal_interactive():
        print("\033[H", end="", flush=True)


def read_cpu_times():
    with open("/proc/stat", "r", encoding="ascii") as handle:
        fields = handle.readline().split()[1:]
    values = [int(field) for field in fields]
    idle = values[3] + values[4]
    total = sum(values)
    return idle, total


def sample_cpu_percent(interval: float) -> float:
    idle1, total1 = read_cpu_times()
    time.sleep(interval)
    idle2, total2 = read_cpu_times()
    total_delta = total2 - total1
    idle_delta = idle2 - idle1
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))


def read_meminfo():
    data = {}
    with open("/proc/meminfo", "r", encoding="ascii") as handle:
        for line in handle:
            key, value = line.split(":", 1)
            data[key] = int(value.strip().split()[0]) * 1024
    return data


def collect_local_rows(sample_interval: float):
    rows = []
    timestamp = datetime.now(timezone.utc).isoformat()
    cpu_count = os.cpu_count() or 1
    meminfo = read_meminfo()

    cpu_percent = sample_cpu_percent(sample_interval)
    rows.append(
        {
            "source": "local",
            "metric": "cpu",
            "label": "LocalCPU",
            "value": cpu_percent,
            "display_value": f"{cpu_percent:.1f}%",
            "detail": f"sampled over {sample_interval:.1f}s across {cpu_count} vCPU",
            "percent_value": cpu_percent,
            "timestamp": timestamp,
        }
    )

    load1, load5, load15 = os.getloadavg()
    load_percent = (load1 / cpu_count) * 100.0
    rows.append(
        {
            "source": "local",
            "metric": "load",
            "label": "Load1",
            "value": load_percent,
            "display_value": f"{load_percent:.1f}%",
            "detail": f"{load1:.2f} / {cpu_count} vCPU (5m {load5:.2f}, 15m {load15:.2f})",
            "percent_value": min(load_percent, 100.0),
            "timestamp": timestamp,
        }
    )

    mem_total = meminfo.get("MemTotal", 0)
    mem_available = meminfo.get("MemAvailable", 0)
    mem_used = max(0, mem_total - mem_available)
    mem_percent = (mem_used / mem_total * 100.0) if mem_total else 0.0
    rows.append(
        {
            "source": "local",
            "metric": "memory",
            "label": "Memory",
            "value": mem_percent,
            "display_value": f"{mem_percent:.1f}%",
            "detail": f"{human_bytes(mem_used)} / {human_bytes(mem_total)} used",
            "percent_value": mem_percent,
            "timestamp": timestamp,
        }
    )

    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)
    swap_used = max(0, swap_total - swap_free)
    swap_percent = (swap_used / swap_total * 100.0) if swap_total else 0.0
    swap_detail = (
        f"{human_bytes(swap_used)} / {human_bytes(swap_total)} used" if swap_total else "swap not configured"
    )
    rows.append(
        {
            "source": "local",
            "metric": "swap",
            "label": "Swap",
            "value": swap_percent,
            "display_value": f"{swap_percent:.1f}%",
            "detail": swap_detail,
            "percent_value": swap_percent,
            "timestamp": timestamp,
        }
    )

    disk = shutil.disk_usage("/")
    disk_percent = (disk.used / disk.total * 100.0) if disk.total else 0.0
    rows.append(
        {
            "source": "local",
            "metric": "disk",
            "label": "Disk(/)",
            "value": disk_percent,
            "display_value": f"{disk_percent:.1f}%",
            "detail": f"{human_bytes(disk.used)} / {human_bytes(disk.total)} used",
            "percent_value": disk_percent,
            "timestamp": timestamp,
        }
    )

    return rows


def parse_metric_spec(spec: str) -> dict:
    if spec.startswith("local:"):
        name = spec.split(":", 1)[1]
        if name not in LOCAL_METRICS:
            raise ValueError(f"Unknown local metric '{name}'. Use --list to see supported local metrics.")
        return {"source": "local", "name": name}

    namespace = "AWS/EC2"
    remainder = spec

    if spec.startswith("aws:"):
        remainder = spec.split(":", 1)[1]
    elif spec.startswith("CWAgent:"):
        namespace = "CWAgent"
        remainder = spec.split(":", 1)[1]
    elif spec.startswith("AWS/EC2:"):
        namespace = "AWS/EC2"
        remainder = spec.split(":", 1)[1]

    parts = remainder.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(
            f"Invalid metric spec '{spec}'. Use MetricName or Namespace:MetricName or MetricName:Stat:Period."
        )

    metric_name = parts[0]
    defaults = COMMON_METRICS_BY_NAMESPACE.get(namespace, {}).get(
        metric_name, {"stat": "Average", "period": 300}
    )
    stat = parts[1] if len(parts) >= 2 and parts[1] else defaults["stat"]
    period = parts[2] if len(parts) == 3 and parts[2] else defaults["period"]

    try:
        period = int(period)
    except ValueError as exc:
        raise ValueError(f"Invalid period in metric spec '{spec}'. Period must be an integer.") from exc

    return {"source": "aws", "namespace": namespace, "name": metric_name, "stat": stat, "period": period}


def print_metric_catalog() -> None:
    print("Local metrics")
    print()
    for name in sorted(LOCAL_METRICS):
        print(f"local:{name:18} {LOCAL_METRICS[name]}")
    for namespace in ("AWS/EC2", "CWAgent"):
        print()
        print(f"{namespace} metrics")
        print()
        for name in sorted(COMMON_METRICS_BY_NAMESPACE[namespace]):
            meta = COMMON_METRICS_BY_NAMESPACE[namespace][name]
            print(f"{name:26} stat={meta['stat']:8} period={meta['period']:>3}s  {meta['description']}")
    print()
    print("Metric syntax")
    print("  ec2m")
    print("  ec2m -m local:memory -m local:disk")
    print("  ec2m -m CPUUtilization")
    print("  ec2m -m AWS/EC2:NetworkIn:Sum:300")
    print("  ec2m -m CWAgent:mem_used_percent")
    print("  ec2m --watch")
    print("  ec2m --live")
    print("  ec2m --doctor")
    print("  ec2m --setup-aws")
    print()
    print("Notes")
    print("  Without -m, the script shows local live metrics plus native AWS/EC2 metrics.")
    print("  Custom AWS metrics default to stat=Average and period=300 if not specified.")
    print("  CWAgent metrics are optional and only work if the CloudWatch Agent runs in background.")
    print("  The script uses the current instance ID dimension.")


def print_aws_setup_guide() -> None:
    print("AWS Setup Guide For ec2m")
    print()
    print("What ec2m needs by default")
    print("  ec2m itself does not run in background.")
    print("  By default it reads live Linux metrics locally and reads native EC2 metrics from CloudWatch on demand.")
    print("  For this default mode, the EC2 instance only needs CloudWatch read permissions.")
    print()
    print("Minimum IAM permission policy for default ec2m usage")
    print()
    print("""{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Sid\": \"ReadEc2CloudWatchMetrics\",
      \"Effect\": \"Allow\",
      \"Action\": [
        \"cloudwatch:GetMetricData\",
        \"cloudwatch:GetMetricStatistics\",
        \"cloudwatch:ListMetrics\"
      ],
      \"Resource\": \"*\"
    }
  ]
}""")
    print()
    print("Trust policy for the EC2 role")
    print()
    print("""{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Effect\": \"Allow\",
      \"Principal\": {
        \"Service\": \"ec2.amazonaws.com\"
      },
      \"Action\": \"sts:AssumeRole\"
    }
  ]
}""")
    print()
    print("How to configure it in AWS web console")
    print("  1. Open IAM -> Policies -> Create policy -> JSON.")
    print("  2. Paste the read policy above and save it, for example as EC2CloudWatchMetricsRead.")
    print("  3. Open IAM -> Roles -> Create role.")
    print("  4. Choose AWS service -> EC2.")
    print("  5. Attach the policy EC2CloudWatchMetricsRead.")
    print("  6. Save the role, for example as EC2CloudWatchReadRole.")
    print("  7. Open EC2 -> Instances -> select this instance.")
    print("  8. Actions -> Security -> Modify IAM role.")
    print("  9. Attach the role EC2CloudWatchReadRole to the instance.")
    print()
    print("Optional CWAgent mode")
    print("  CWAgent is only needed if you want OS metrics stored in CloudWatch itself, such as")
    print("  mem_used_percent, disk_used_percent, and swap_used_percent from the CWAgent namespace.")
    print("  That mode requires a background service: amazon-cloudwatch-agent.")
    print("  If you do not want background publishing, keep CWAgent disabled and use local:* metrics instead.")
    print()
    print("Permissions for optional CWAgent mode")
    print("  Simplest AWS web-console option: attach the managed policy CloudWatchAgentServerPolicy to the instance role.")
    print("  Minimal custom capability needed for publishing is cloudwatch:PutMetricData.")
    print()
    print("How to verify after setup")
    print("  ec2m --doctor")
    print("  ec2m")
    print("  ec2m --live")
    print()
    print("Recommended usage model")
    print("  Default: use ec2m on demand with local:* plus AWS/EC2 metrics.")
    print("  Optional: enable CWAgent only if you explicitly want OS metrics persisted in CloudWatch.")


def print_release_info() -> None:
    print("ec2m Release Info")
    print()
    print(f"Version:         {VERSION}")
    print(f"Release date:    {RELEASE_DATE}")
    print(f"Channel:         {RELEASE_CHANNEL}")
    print("Install model:   single-file installer with Python dependency bootstrap")
    print("Default mode:    on-demand local metrics plus native AWS/EC2 CloudWatch metrics")
    print("Optional mode:   CWAgent background publisher for OS metrics in CloudWatch")
    print("Main commands:   ec2m, ec2m --live, ec2m --doctor, ec2m --setup-aws")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ec2m",
        description="Show local live metrics and AWS/EC2 CloudWatch metrics for the current EC2 instance.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-m",
        "--metric",
        action="append",
        default=[],
        help="Metric spec. Repeatable. Examples: local:memory, CPUUtilization, CWAgent:mem_used_percent.",
    )
    parser.add_argument(
        "-w",
        "--window-minutes",
        type=int,
        default=20,
        help="How far back to search CloudWatch datapoints. Default: 20.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show supported local metrics and common CloudWatch metrics.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON output instead of tables.",
    )
    parser.add_argument(
        "-r",
        "--refresh",
        type=float,
        default=0.0,
        help="Refresh every N seconds until interrupted.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Compact continuously refreshing dashboard. Defaults to 2s refresh.",
    )
    parser.add_argument(
        "--live",
        "--online",
        action="store_true",
        help="Full-screen live dashboard with colors and usage bars. Defaults to 2s refresh.",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=0.2,
        help="Sampling interval in seconds for local CPU usage. Default: 0.2.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run connectivity and permission checks for metadata, CloudWatch, and optional CWAgent.",
    )
    parser.add_argument(
        "--setup-aws",
        "--aws-setup",
        action="store_true",
        help="Show the built-in AWS IAM and EC2 setup guide for this tool.",
    )
    parser.add_argument(
        "--release-info",
        "--about",
        action="store_true",
        help="Show release metadata and packaging details for this build.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def run_command(command):
    try:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
        return True, completed.stdout.strip() or completed.stderr.strip()
    except subprocess.CalledProcessError as exc:
        output = exc.stdout.strip() or exc.stderr.strip() or str(exc)
        return False, output


def print_doctor_row(name: str, ok: bool, detail: str):
    status = "OK" if ok else "FAIL"
    print(f"{name:24} {status:4}  {detail}")


def run_doctor(instance_id: str, region: str, instance_type: str) -> int:
    print(f"Instance:     {instance_id}")
    print(f"InstanceType: {instance_type}")
    print(f"Region:       {region}")
    print()
    print(f"{'Check':24} {'Status':4}  Detail")
    print(f"{'-' * 24} {'-' * 6}  {'-' * 60}")

    session = boto3.Session(region_name=region)
    cloudwatch = session.client("cloudwatch")
    sts = session.client("sts")
    failures = 0

    try:
        metadata("/latest/meta-data/instance-id")
        print_doctor_row("IMDSv2", True, "instance metadata reachable")
    except Exception as exc:
        print_doctor_row("IMDSv2", False, str(exc))
        failures += 1

    try:
        identity = sts.get_caller_identity()
        print_doctor_row("STS identity", True, identity["Arn"])
    except (BotoCoreError, ClientError, Exception) as exc:
        print_doctor_row("STS identity", False, str(exc))
        failures += 1

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=20)

    try:
        response = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "cpu",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/EC2",
                            "MetricName": "CPUUtilization",
                            "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                        },
                        "Period": 60,
                        "Stat": "Average",
                    },
                    "ReturnData": True,
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            ScanBy="TimestampDescending",
        )
        values = response["MetricDataResults"][0]["Values"]
        detail = f"CPUUtilization datapoints={len(values)}"
        print_doctor_row("CloudWatch read", True, detail)
    except (BotoCoreError, ClientError, Exception) as exc:
        print_doctor_row("CloudWatch read", False, str(exc))
        failures += 1

    try:
        cloudwatch.put_metric_data(
            Namespace="CodexPermissionCheck",
            MetricData=[
                {
                    "MetricName": "Ping",
                    "Value": 1.0,
                    "Unit": "Count",
                    "Timestamp": end_time,
                }
            ],
        )
        print_doctor_row("CloudWatch write", True, "cloudwatch:PutMetricData allowed")
    except (BotoCoreError, ClientError, Exception) as exc:
        print_doctor_row("CloudWatch write", False, str(exc))
        failures += 1

    ok, detail = run_command(["systemctl", "is-active", "amazon-cloudwatch-agent"])
    cwagent_active = ok and detail == "active"
    if cwagent_active:
        print_doctor_row("CWAgent service", True, "active")

        try:
            paginator = cloudwatch.get_paginator("list_metrics")
            metric_names = set()
            for page in paginator.paginate(
                Namespace="CWAgent",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            ):
                for metric in page.get("Metrics", []):
                    metric_names.add(metric["MetricName"])

            if metric_names:
                print_doctor_row("CWAgent metrics", True, ", ".join(sorted(metric_names)))
            else:
                print_doctor_row("CWAgent metrics", False, "no metrics visible in namespace CWAgent yet")
                failures += 1
        except (BotoCoreError, ClientError, Exception) as exc:
            print_doctor_row("CWAgent metrics", False, str(exc))
            failures += 1

        ok, detail = run_command(["tail", "-n", "20", "/opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log"])
        if ok and "AccessDenied" in detail and "PutMetricData" in detail:
            print_doctor_row("CWAgent logs", False, "agent log contains AccessDenied for PutMetricData")
            failures += 1
        elif ok:
            print_doctor_row("CWAgent logs", True, "no recent PutMetricData access errors")
        else:
            print_doctor_row("CWAgent logs", False, detail)
            failures += 1
    else:
        print_doctor_row("CWAgent service", True, "disabled by design, optional background publisher is off")
        print_doctor_row("CWAgent metrics", True, "skipped because CWAgent is not running")
        print_doctor_row("CWAgent logs", True, "skipped because CWAgent is not running")

    return 1 if failures else 0


def format_aws_value(namespace: str, metric_name: str, value, stat: str, period: int, instance_type: str):
    if value == "NO_DATA":
        return "NO_DATA", "no datapoint in selected window", None

    numeric = float(value)

    if metric_name == "CPUUtilization" or metric_name in PERCENT_METRICS:
        return f"{numeric:.1f}%", "percent of maximum", numeric

    if metric_name == "CPUCreditBalance":
        credit_limit = CPU_CREDIT_LIMITS.get(instance_type)
        if credit_limit:
            percent = (numeric / credit_limit) * 100.0
            return f"{numeric:.2f}", f"{percent:.1f}% of {credit_limit:g} credit max", percent
        return f"{numeric:.2f}", "credit max unknown for this instance type", None

    if metric_name in STATUS_METRICS:
        percent = numeric * 100.0
        return f"{int(numeric)}", f"{percent:.0f}% of failure threshold", percent

    if metric_name in BYTE_METRICS and stat == "Sum":
        per_second = numeric / period if period else numeric
        return human_bytes(per_second) + "/s", f"{human_bytes(numeric)} total over {period}s", None

    if metric_name in COUNT_METRICS and stat == "Sum":
        per_second = numeric / period if period else numeric
        return human_count(per_second) + "/s", f"{human_count(numeric)} total over {period}s", None

    return f"{numeric:.4f}".rstrip("0").rstrip("."), f"{namespace}, stat={stat}, period={period}s", None


def collect_aws_rows(aws_metrics, window_minutes: int, instance_id: str, region: str, instance_type: str):
    if not aws_metrics:
        return []

    session = boto3.Session(region_name=region)
    cloudwatch = session.client("cloudwatch")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=window_minutes)

    queries = []
    query_map = {}
    for index, metric in enumerate(aws_metrics, start=1):
        query_id = f"m{index}"
        query_map[query_id] = metric
        queries.append(
            {
                "Id": query_id,
                "MetricStat": {
                    "Metric": {
                        "Namespace": metric["namespace"],
                        "MetricName": metric["name"],
                        "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                    },
                    "Period": metric["period"],
                    "Stat": metric["stat"],
                },
                "ReturnData": True,
            }
        )

    response = cloudwatch.get_metric_data(
        MetricDataQueries=queries,
        StartTime=start_time,
        EndTime=end_time,
        ScanBy="TimestampDescending",
    )

    rows = []
    for result in response["MetricDataResults"]:
        metric = query_map[result["Id"]]
        value = result["Values"][0] if result["Values"] else "NO_DATA"
        display_value, detail, percent_value = format_aws_value(
            metric["namespace"], metric["name"], value, metric["stat"], metric["period"], instance_type
        )
        rows.append(
            {
                "source": "aws",
                "namespace": metric["namespace"],
                "metric": metric["name"],
                "label": metric["name"],
                "stat": metric["stat"],
                "period": metric["period"],
                "value": value,
                "display_value": display_value,
                "detail": detail,
                "percent_value": percent_value,
                "timestamp": result["Timestamps"][0].isoformat() if result["Timestamps"] else "NO_TIMESTAMP",
            }
        )

    order = [(metric["namespace"], metric["name"]) for metric in aws_metrics]
    rows.sort(key=lambda row: order.index((row["namespace"], row["metric"])))
    return rows


def render_table(instance_id: str, region: str, instance_type: str, window_minutes: int, rows):
    print(f"Instance:     {instance_id}")
    print(f"InstanceType: {instance_type}")
    print(f"Region:       {region}")
    print(f"Window:       last {window_minutes} minutes")
    print(f"Generated:    {datetime.now(timezone.utc).isoformat()}")
    print()

    local_rows = [row for row in rows if row["source"] == "local"]
    aws_rows = [row for row in rows if row["source"] == "aws"]

    if local_rows:
        print("Local")
        print(f"{'Metric':16} {'Value':14} Details")
        print(f"{'-' * 16} {'-' * 14} {'-' * 48}")
        for row in local_rows:
            print(f"{row['label']:16} {row['display_value']:14} {row['detail']}")
        print()

    for namespace in ["AWS/EC2", "CWAgent"]:
        namespace_rows = [row for row in aws_rows if row["namespace"] == namespace]
        if not namespace_rows:
            continue
        print(namespace)
        print(f"{'Metric':26} {'Stat':8} {'Period':>6} {'Value':18} Details")
        print(f"{'-' * 26} {'-' * 8} {'-' * 6} {'-' * 18} {'-' * 48}")
        for row in namespace_rows:
            period = f"{row['period']}s"
            print(f"{row['label']:26} {row['stat']:8} {period:>6} {row['display_value']:18} {row['detail']}")
            print(f"{'':26} {'':8} {'':6} {'':18} {row['timestamp']}")
        print()

    cwagent_rows = [row for row in aws_rows if row["namespace"] == "CWAgent"]
    if cwagent_rows and all(row["value"] == "NO_DATA" for row in cwagent_rows):
        print("Hint: CWAgent metrics are configured but not arriving yet. Run `ec2m --doctor` to check")
        print("      CloudWatch Agent status and whether the instance role can call PutMetricData.")
        print()


def render_watch(instance_id: str, region: str, instance_type: str, rows):
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{generated}  {instance_id}  {instance_type}  {region}")
    print()

    def short_line(title, items):
        if not items:
            return
        payload = " | ".join(items)
        print(f"{title}: {payload}")

    local_rows = [row for row in rows if row["source"] == "local"]
    aws_rows = [row for row in rows if row["source"] == "aws"]

    short_line(
        "Local",
        [f"{row['label']} {row['display_value']}" for row in local_rows],
    )
    short_line(
        "AWS/EC2",
        [f"{row['label']} {row['display_value']}" for row in aws_rows if row["namespace"] == "AWS/EC2"],
    )
    short_line(
        "CWAgent",
        [f"{row['label']} {row['display_value']}" for row in aws_rows if row["namespace"] == "CWAgent"],
    )
    print()
    print("Ctrl+C to stop")


def render_live(instance_id: str, region: str, instance_type: str, window_minutes: int, rows, refresh_interval: float):
    width = max(90, shutil.get_terminal_size((100, 24)).columns)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = paint("EC2 Live Dashboard", "bold", "cyan")
    refresh_text = f"refresh {refresh_interval:.1f}s" if refresh_interval > 0 else "single snapshot"
    print(title)
    print("=" * min(width, 100))
    print(
        f"{paint('Instance', 'bold')}: {instance_id}   "
        f"{paint('Type', 'bold')}: {instance_type}   "
        f"{paint('Region', 'bold')}: {region}"
    )
    print(
        f"{paint('Generated', 'bold')}: {generated}   "
        f"{paint('Window', 'bold')}: last {window_minutes}m   "
        f"{paint('Mode', 'bold')}: {refresh_text}"
    )
    print()

    local_rows = [row for row in rows if row["source"] == "local"]
    ec2_rows = [row for row in rows if row["source"] == "aws" and row["namespace"] == "AWS/EC2"]
    cw_rows = [row for row in rows if row["source"] == "aws" and row["namespace"] == "CWAgent"]

    def print_section(name, section_rows):
        if not section_rows:
            return
        print(paint(name, "bold"))
        for row in section_rows:
            label = f"{row['label']:<18}"
            percent_value = row.get("percent_value")
            if percent_value is not None:
                bar = percent_bar(percent_value)
                value = paint(f"{row['display_value']:>8}", percent_color(percent_value), "bold")
                detail = row["detail"]
                age = short_timestamp(row["timestamp"])
                print(f"  {label} {paint(bar, percent_color(percent_value))} {value}  {detail}  @ {age}")
            else:
                value = paint(f"{row['display_value']:>12}", "bold")
                detail = row["detail"]
                age = short_timestamp(row["timestamp"])
                print(f"  {label} {value}  {detail}  @ {age}")
        print()

    print_section("Local", local_rows)
    print_section("AWS/EC2", ec2_rows)
    print_section("CWAgent", cw_rows)
    print(paint("Ctrl+C", "bold") + " to stop")


def collect_rows(parsed_specs, instance_id: str, region: str, instance_type: str, window_minutes: int, sample_interval: float):
    local_specs = [spec for spec in parsed_specs if spec["source"] == "local"]
    aws_specs = [spec for spec in parsed_specs if spec["source"] == "aws"]

    rows = []
    if local_specs:
        local_rows = collect_local_rows(sample_interval)
        selected = {spec["name"] for spec in local_specs}
        rows.extend([row for row in local_rows if row["metric"] in selected])

    if aws_specs:
        rows.extend(collect_aws_rows(aws_specs, window_minutes, instance_id, region, instance_type))

    return rows


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        print_metric_catalog()
        return 0

    if args.setup_aws:
        print_aws_setup_guide()
        return 0

    if args.release_info:
        print_release_info()
        return 0

    try:
        parsed_specs = [parse_metric_spec(spec) for spec in (args.metric or DEFAULT_SPECS)]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    instance_id = metadata("/latest/meta-data/instance-id")
    instance_type = metadata("/latest/meta-data/instance-type")
    region = json.loads(metadata("/latest/dynamic/instance-identity/document"))["region"]

    if args.doctor:
        return run_doctor(instance_id, region, instance_type)

    refresh_interval = args.refresh
    if (args.watch or args.live) and refresh_interval <= 0:
        refresh_interval = 2.0

    def run_once():
        rows = collect_rows(
            parsed_specs,
            instance_id=instance_id,
            region=region,
            instance_type=instance_type,
            window_minutes=args.window_minutes,
            sample_interval=args.sample_interval,
        )

        if args.json:
            print(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "instance_type": instance_type,
                        "region": region,
                        "window_minutes": args.window_minutes,
                        "rows": rows,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
            )
        elif args.watch:
            render_watch(instance_id, region, instance_type, rows)
        elif args.live:
            render_live(instance_id, region, instance_type, args.window_minutes, rows, refresh_interval)
        else:
            render_table(instance_id, region, instance_type, args.window_minutes, rows)

    def render_frame() -> str:
        buffer = io.StringIO()
        previous_stdout = sys.stdout
        try:
            sys.stdout = buffer
            run_once()
        finally:
            sys.stdout = previous_stdout
        return buffer.getvalue()

    interactive_refresh = refresh_interval > 0 and (args.watch or args.live) and terminal_interactive()

    try:
        if interactive_refresh:
            enter_alt_screen()

        if refresh_interval > 0:
            while True:
                if interactive_refresh:
                    frame = render_frame()
                    redraw_frame()
                    sys.stdout.write(frame)
                    sys.stdout.write("\033[J")
                    sys.stdout.flush()
                else:
                    run_once()
                    sys.stdout.flush()
                time.sleep(refresh_interval)
        else:
            run_once()
    except KeyboardInterrupt:
        return 130
    finally:
        if interactive_refresh:
            leave_alt_screen()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
