import csv
import os
import time
import socket
import subprocess
from datetime import datetime

import paho.mqtt.client as mqtt


# =========================
# CONFIG
# =========================
BROKER_HOST = "localhost"
BROKER_PORT = 4433
INTERFACE = "lo"
CSV_FILE = "results.csv"

ALGORITHMS = ["KYBER_TLS"]
# For now these are labels only.
# Later, when you actually switch crypto configs, this field will reflect real runs.

PACKET_LOSS_VALUES = [0, 1, 2, 3, 5, 7, 10]      # percent
JITTER_VALUES = [0, 20, 50]                      # ms
BASE_DELAY_MS = 50                               # fixed base delay
TRIALS_PER_SCENARIO = 30
TIMEOUT_SECONDS = 5


# =========================
# HELPERS: TC / NETEM
# =========================
def run_command(cmd: str) -> None:
    """Run a shell command and raise error if it fails."""
    subprocess.run(cmd, shell=True, check=True)


def clear_netem(interface: str) -> None:
    """Remove existing qdisc rule if present."""
    cmd = f"sudo tc qdisc del dev {interface} root"
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def apply_netem(interface: str, delay_ms: int = 0, jitter_ms: int = 0, loss_pct: int = 0) -> None:
    """
    Apply netem conditions.
    Examples:
      delay only: delay 50ms
      delay + jitter: delay 50ms 20ms
      loss only: loss 5%
      both: delay 50ms 20ms loss 5%
    """
    clear_netem(interface)

    parts = [f"sudo tc qdisc add dev {interface} root netem"]

    if delay_ms > 0 and jitter_ms > 0:
        parts.append(f"delay {delay_ms}ms {jitter_ms}ms")
    elif delay_ms > 0:
        parts.append(f"delay {delay_ms}ms")

    if loss_pct > 0:
        parts.append(f"loss {loss_pct}%")

    cmd = " ".join(parts)
    run_command(cmd)


# =========================
# MQTT TRIAL
# =========================
def run_handshake_trial(broker_host: str, broker_port: int, timeout_sec: int = 5):
    import subprocess
    import time

    start_time = time.perf_counter()

    try:
        cmd = [
            "/usr/local/bin/openssl",
            "s_client",
            "-connect", f"{broker_host}:{broker_port}",
            "-groups", "p384_kyber768",
            "-brief"
        ]

        result = subprocess.run(
            cmd,
            input=b"Q\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec
        )

        end_time = time.perf_counter()
        handshake_ms = (end_time - start_time) * 1000.0

        output = (
            result.stdout.decode(errors="ignore") +
            result.stderr.decode(errors="ignore")
        )

        # Success detection
        if (
            "CONNECTION ESTABLISHED" in output or
            "Protocol version" in output or
            result.returncode == 0
        ):
            return {
                "success": 1,
                "handshake_time_ms": round(handshake_ms, 3),
                "error_reason": ""
            }

        return {
            "success": 0,
            "handshake_time_ms": round(handshake_ms, 3),
            "error_reason": output[:200].replace("\n", " ")
        }

    except subprocess.TimeoutExpired:
        end_time = time.perf_counter()
        return {
            "success": 0,
            "handshake_time_ms": round((end_time - start_time) * 1000.0, 3),
            "error_reason": "timeout"
        }

    except Exception as e:
        end_time = time.perf_counter()
        return {
            "success": 0,
            "handshake_time_ms": round((end_time - start_time) * 1000.0, 3),
            "error_reason": str(e)
        }


# =========================
# CSV SETUP
# =========================
def initialize_csv(csv_file: str) -> None:
    """Create CSV with header if it does not exist."""
    if not os.path.exists(csv_file):
        with open(csv_file, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "algorithm",
                "packet_loss_percent",
                "base_delay_ms",
                "jitter_ms",
                "trial_number",
                "success",
                "handshake_time_ms",
                "error_reason"
            ])


def append_result(csv_file: str, row: dict) -> None:
    """Append one result row to CSV."""
    with open(csv_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            row["timestamp"],
            row["algorithm"],
            row["packet_loss_percent"],
            row["base_delay_ms"],
            row["jitter_ms"],
            row["trial_number"],
            row["success"],
            row["handshake_time_ms"],
            row["error_reason"]
        ])


# =========================
# MAIN EXPERIMENT LOOP
# =========================
def main():
    initialize_csv(CSV_FILE)

    total_runs = len(ALGORITHMS) * len(PACKET_LOSS_VALUES) * len(JITTER_VALUES) * TRIALS_PER_SCENARIO
    current_run = 0

    print(f"Starting experiment. Total runs: {total_runs}")

    try:
        for algorithm in ALGORITHMS:
            # IMPORTANT:
            # Right now "algorithm" is only a label.
            # Later you will insert real logic here to switch between ECC and KYBER configs.

            for loss in PACKET_LOSS_VALUES:
                for jitter in JITTER_VALUES:
                    print(f"\nScenario => Algorithm={algorithm}, Loss={loss}%, Delay={BASE_DELAY_MS}ms, Jitter={jitter}ms")

                    # Apply network condition once per scenario
                    apply_netem(
                        interface=INTERFACE,
                        delay_ms=BASE_DELAY_MS,
                        jitter_ms=jitter,
                        loss_pct=loss
                    )

                    # Small pause so the qdisc change is fully in effect
                    time.sleep(0.2)

                    for trial in range(1, TRIALS_PER_SCENARIO + 1):
                        current_run += 1
                        result = run_handshake_trial(
                            broker_host=BROKER_HOST,
                            broker_port=BROKER_PORT,
                            timeout_sec=TIMEOUT_SECONDS
                        )

                        row = {
                            "timestamp": datetime.now().isoformat(),
                            "algorithm": algorithm,
                            "packet_loss_percent": loss,
                            "base_delay_ms": BASE_DELAY_MS,
                            "jitter_ms": jitter,
                            "trial_number": trial,
                            "success": result["success"],
                            "handshake_time_ms": result["handshake_time_ms"],
                            "error_reason": result["error_reason"]
                        }

                        append_result(CSV_FILE, row)

                        print(
                            f"[{current_run}/{total_runs}] "
                            f"{algorithm} | loss={loss}% | jitter={jitter}ms | "
                            f"trial={trial} | success={result['success']} | "
                            f"time={result['handshake_time_ms']} ms | error={result['error_reason']}"
                        )

                        # Tiny pause between trials to reduce weird back-to-back artifacts
                        time.sleep(0.1)

    finally:
        clear_netem(INTERFACE)
        print("\nExperiment finished. NetEm cleared.")


if __name__ == "__main__":
    main()
