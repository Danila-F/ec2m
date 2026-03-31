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


def require_aws_sdk():
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:
        raise RuntimeError(
            "AWS metrics require boto3 and botocore. Install ec2m with install-ec2m.sh "
            "or run: pip install boto3 botocore"
        ) from exc

    return boto3, BotoCoreError, ClientError


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
    print("  9. Attach the ro