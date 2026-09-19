# Accounts-Enumeration

import os
os.environ["PYTHONIOENCODING"] = "UTF8"
os.environ["COLORTERM"] = "truecolor"
os.environ["TERM"] = "xterm-256color"
import sys
import httpx
import time
import statistics
import random
import json
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    TimeRemainingColumn, MofNCompleteColumn, TaskProgressColumn,
)
from rich.text import Text
from rich.box import ROUNDED, HEAVY, DOUBLE
from rich.align import Align
from rich.columns import Columns
from rich.theme import Theme

CUSTOM_THEME = Theme({
    "info":    "bright_cyan",
    "warn":    "bold bright_yellow",
    "danger":  "bold bright_red",
    "success": "bold bright_green",
    "muted":   "dim white",
    "accent":  "bold magenta",
    "accent2": "bold bright_blue",
})

console = Console(
    theme=CUSTOM_THEME,
    force_terminal=True,
    color_system="truecolor",
    legacy_windows=False,
    safe_box=False,
    highlight=False,
)

CONFIG_FILE = "config.json"
DEFAULT_SAMPLES = 12

HEADERS = {
    "Accept-Encoding": "gzip",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    console.print(f"[success]✔ Configuration persisted →[/success] [info]{CONFIG_FILE}[/info]")


def calculate_mad(data, med):
    return statistics.median([abs(x - med) for x in data])


def percentile(data, p):
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize(durations, lengths):
    med_t = statistics.median(durations)
    med_l = statistics.median(lengths)
    return {
        "median_time": med_t,
        "mad_time":    calculate_mad(durations, med_t),
        "mean_time":   statistics.mean(durations),
        "stdev_time":  statistics.pstdev(durations) if len(durations) > 1 else 0.0,
        "p95_time":    percentile(durations, 95),
        "min_time":    min(durations),
        "max_time":    max(durations),
        "jitter":      max(durations) - min(durations),
        "median_len":  med_l,
        "mad_len":     calculate_mad(lengths, med_l),
        "statuses":    None,
        "samples":     list(durations),
    }


def sparkline(values, chars="▁▂▃▄▅▆▇█"):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo if hi != lo else 1
    return "".join(chars[int((v - lo) / span * (len(chars) - 1))] for v in values)


def colorize_spark(spark):
    colors = ["bright_blue", "bright_cyan", "bright_green",
              "bright_yellow", "bright_red"]
    out = Text()
    for ch in spark:
        idx = min(len(colors) - 1, "▁▂▃▄▅▆▇█".index(ch) // 2) if ch in "▁▂▃▄▅▆▇█" else 0
        out.append(ch, style=colors[idx])
    return out


def measure_endpoint_stats(client, url, payload, samples, label="Target"):
    durations, lengths, statuses = [], [], set()

    progress = Progress(
        SpinnerColumn(spinner_name="dots12", style="accent"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=28, style="grey30",
                  complete_style="bright_green",
                  finished_style="bright_cyan",
                  pulse_style="bright_magenta"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TextColumn("[info]⏱ {task.elapsed:.1f}s"),
        TextColumn("[muted]ETA"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
        expand=False,
    )

    with progress:
        task = progress.add_task(f"[magenta]◉[/magenta] {label[:28]:<28}", total=samples)
        for _ in range(samples):
            t0 = time.perf_counter()
            try:
                resp = client.post(url, json=payload, headers=HEADERS)
                t1 = time.perf_counter()
                durations.append((t1 - t0) * 1000)
                lengths.append(len(resp.content))
                statuses.add(resp.status_code)
            except Exception:
                durations.append(0.0)
                lengths.append(0)
                statuses.add(-1)
            progress.update(task, advance=1)
            time.sleep(random.uniform(0.25, 0.55))

    stats = summarize(durations, lengths)
    stats["statuses"] = statuses
    return stats


def section(title, icon="▸", color="bright_cyan"):
    console.print()
    console.rule(f"[bold {color}]{icon} {title}[/bold {color}]", style=color, align="left")
    console.print()


def keyval(label, value, lc="cyan", vc="bright_white"):
    return Text.assemble((f"{label:<14}", f"bold {lc}"), (f"{value}", vc))


def verdict_for(fake, target):
    time_diff = abs(target["median_time"] - fake["median_time"])
    len_diff  = abs(target["median_len"]  - fake["median_len"])
    denom     = fake["mad_time"] + 0.1
    sep_score = time_diff / denom

    if len_diff > 0:
        return ("HOT", "🔥 HIGH ANOMALY",
                "Response length shift → schema/state leak", "red"), time_diff, len_diff, sep_score
    if sep_score > 3.0:
        return ("MID", f"⚡ LIKELY ANOMALY  (Sep {sep_score:.2f} > 3.0)",
                "Timing deviation exceeds noise floor", "yellow"), time_diff, len_diff, sep_score
    return ("OK", "🛡️ CLEAN / NO DEVIATION",
            "Within statistical noise margin", "green"), time_diff, len_diff, sep_score


def print_result_table(fake, target, label):
    (vkey, vtext, vdesc, vcolor), time_diff, len_diff, sep = verdict_for(fake, target)

    fake_len_int   = int(round(fake["median_len"]))
    target_len_int = int(round(target["median_len"]))
    len_diff_int   = int(round(len_diff))

    table = Table(
        title=f"[bold bright_magenta]✦ ChronOracle Report — [/bold bright_magenta][bold bright_cyan]{label}[/bold bright_cyan]",
        header_style="bold white on grey23",
        border_style="bright_cyan",
        box=ROUNDED,
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("Metric", style="bold cyan", width=18, no_wrap=True)
    table.add_column("FAKE baseline", justify="right", style="bright_blue")
    table.add_column("TARGET probe",  justify="right", style="bright_magenta")
    table.add_column("Δ Delta",       justify="right")
    table.add_column("Telemetry",     justify="left", style="muted")

    def row(name, fv, tv, dv, style, extra=""):
        table.add_row(name, fv, tv, Text(dv, style=style), extra)

    row("Median (ms)",
        f"{fake['median_time']:.2f}", f"{target['median_time']:.2f}",
        f"{time_diff:+.2f}",
        "bold red" if time_diff > 5 else ("yellow" if time_diff > 2 else "green"),
        f"sep={sep:.2f}")

    row("Mean (ms)",
        f"{fake['mean_time']:.2f}", f"{target['mean_time']:.2f}",
        f"{target['mean_time'] - fake['mean_time']:+.2f}", "bright_cyan")

    row("MAD (spread)",
        f"{fake['mad_time']:.2f}", f"{target['mad_time']:.2f}",
        f"{target['mad_time'] - fake['mad_time']:+.2f}", "dim cyan")

    row("Stddev",
        f"{fake['stdev_time']:.2f}", f"{target['stdev_time']:.2f}",
        f"{target['stdev_time'] - fake['stdev_time']:+.2f}", "bright_blue")

    row("P95 (ms)",
        f"{fake['p95_time']:.2f}", f"{target['p95_time']:.2f}",
        f"{target['p95_time'] - fake['p95_time']:+.2f}", "blue")

    row("Min / Max",
        f"{fake['min_time']:.1f}/{fake['max_time']:.1f}",
        f"{target['min_time']:.1f}/{target['max_time']:.1f}",
        f"J Δ {target['jitter'] - fake['jitter']:+.1f}", "magenta")

    row("Payload (B)",
        f"{fake_len_int}", f"{target_len_int}",
        f"{len_diff_int:+d}",
        "bold bright_red" if len_diff_int else "dim green")

    def fmt_statuses(s):
        return " ".join(
            f"[black on bright_green] {x} [/]" if x == 200
            else f"[black on bright_yellow] {x} [/]" if x in (301, 302, 403)
            else f"[white on red] {x} [/]" if x >= 400 or x < 0
            else f"[white on grey30] {x} [/]"
            for x in sorted(s)
        )
    table.add_row("Status", fmt_statuses(fake["statuses"]), fmt_statuses(target["statuses"]),
                  Text(f"{sep:.2f}", style="bold cyan"), "sep-ratio")

    console.print()
    console.print(table)

    spark_f = sparkline(fake["samples"])
    spark_t = sparkline(target["samples"])
    console.print()
    console.print(Columns([
        Panel(
            Group(
                Text("FAKE  baseline", style="bold bright_blue"),
                colorize_spark(spark_f),
                Text(f"{len(fake['samples'])} samples", style="muted"),
            ),
            border_style="bright_blue", box=ROUNDED, padding=(0, 2), expand=True,
        ),
        Panel(
            Group(
                Text("TARGET  probe", style="bold bright_magenta"),
                colorize_spark(spark_t),
                Text(f"{len(target['samples'])} samples", style="muted"),
            ),
            border_style="bright_magenta", box=ROUNDED, padding=(0, 2), expand=True,
        ),
    ]))

    verdict_body = Text.assemble(
        (f"  {vtext}\n", f"bold {vcolor}"),
        (f"  {vdesc}\n", "dim white"),
        ("  Sep-Score: ", "bold cyan"), (f"{sep:.2f}", f"bold {vcolor}"),
        ("   Time Δ: ", "bold cyan"), (f"{time_diff:+.2f} ms", f"bold {vcolor}"),
        ("   Len Δ: ", "bold cyan"),  (f"{len_diff_int:+d} B", f"bold {vcolor}"),
    )
    console.print(Panel(
        verdict_body,
        title=f"[bold {vcolor}]◈ VERDICT ◈[/bold {vcolor}]",
        border_style=vcolor,
        box=HEAVY,
        padding=(0, 1),
    ))
    console.print()


def setup_config():
    cfg = load_config()
    if cfg:
        body = Group(
            keyval("Target URL", cfg.get("target_url", "?"), "bright_cyan", "bright_white"),
            keyval("Samples", str(cfg.get("samples", DEFAULT_SAMPLES)), "bright_yellow", "bright_yellow"),
        )
        console.print(Panel(body, title="[bold bright_green]⛁ Saved Configuration[/bold bright_green]",
                            border_style="bright_green", box=ROUNDED, padding=(0, 2)))
        if console.input("[bold yellow][?] Use saved config? [Y/n]: [/bold yellow]").strip().lower() != "n":
            return cfg

    section("NEW RUN CONFIGURATION", "◆", "bright_magenta")
    target_url = console.input("[cyan]▶ Target endpoint URL: [/cyan]").strip() \
                 or "https://api.target.com/v1/auth/password-reset"
    raw = console.input(f"[cyan]▶ Samples per probe [default {DEFAULT_SAMPLES}]: [/cyan]").strip()
    samples = int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_SAMPLES

    cfg = {"target_url": target_url, "samples": samples}
    save_config(cfg)
    return cfg


def choose_field():
    section("INPUT FIELD IDENTIFIER", "◆", "bright_blue")
    console.print("  [accent][1][/accent] [bright_white]Email[/bright_white]   "
                  "[accent][2][/accent] [bright_white]Username[/bright_white]   "
                  "[accent][3][/accent] [bright_white]Phone[/bright_white]\n")
    choice = console.input("[yellow]▶ Select [1-3, default 1]: [/yellow]").strip() or "1"
    field_map = {
        "1": ("email",    "ghost_no_exist_998877@target.com"),
        "2": ("username", "ghost_xyz_9988"),
        "3": ("phone",    "+19998887776"),
    }
    return field_map.get(choice, field_map["1"])


def main():
    cfg = setup_config()
    target_url = cfg["target_url"]
    samples    = cfg["samples"]

    field_key, default_fake = choose_field()
    fake_val = console.input(
        f"[cyan]▶ FAKE baseline {field_key} [default: {default_fake}]: [/cyan]"
    ).strip() or default_fake
    fake_payload = {field_key: fake_val}

    with httpx.Client(timeout=10.0) as client:
        section("PHASE 1 — BASELINE PROBE", "◐", "bright_blue")
        fake_stats = measure_endpoint_stats(
            client, target_url, fake_payload, samples, f"FAKE:{fake_val}"
        )
        console.print(f"[success]✔ Baseline established[/success]  "
                      f"[muted]median[/muted] [bright_blue]{fake_stats['median_time']:.2f}ms[/bright_blue]  "
                      f"[muted]MAD[/muted] [bright_blue]{fake_stats['mad_time']:.2f}ms[/bright_blue]")
        time.sleep(0.6)

        section("PHASE 2 — TARGET PROBE", "◑", "bright_magenta")
        target_val = console.input(f"[cyan]▶ TARGET {field_key} to analyze: [/cyan]").strip()
        if not target_val:
            console.print("[danger]✖ No target provided. Aborting.[/danger]")
            return

        target_stats = measure_endpoint_stats(
            client, target_url, {field_key: target_val}, samples, target_val
        )

        print_result_table(fake_stats, target_stats, target_val)

    exit_flow(cfg)


def exit_flow(cfg):
    if console.input("[bold yellow][?] Modify saved configuration? [y/N]: [/bold yellow]").strip().lower() == "y":
        nu = console.input(f"[cyan]New target URL [{cfg['target_url']}]: [/cyan]").strip()
        if nu:
            cfg["target_url"] = nu
        ns = console.input(f"[cyan]New sample count [{cfg['samples']}]: [/cyan]").strip()
        if ns.isdigit():
            cfg["samples"] = int(ns)
        save_config(cfg)

    console.print(Panel(
        Align.center(Text.assemble(
            ("Session Terminated\n", "bold bright_green"),
            ("Stay sharp, bug hunter 🎯", "bright_yellow"),
        )),
        border_style="bright_green",
        box=DOUBLE,
        padding=(1, 4),
    ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[danger]⚠ Interrupted by user.[/danger]")
        sys.exit(130)