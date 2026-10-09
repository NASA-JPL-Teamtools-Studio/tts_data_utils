"""Throwaway DTAT demo for deriving and filtering telemetry channels.

Run from the repository root with::

    python examples/channel_derivation_filtering_demo.py

The script writes two interactive Plotly/DTAT HTML plots to ``demo_output``.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from tts_data_utils.core.data_frame import TtsDataFrame
from tts_dtat.plot import make_stacked_graph


OUTPUT_DIR = Path(__file__).resolve().parent / "demo_output"


def make_telemetry(sample_count=1200, seed=7):
    rng = np.random.default_rng(seed)
    times = pd.date_range("2026-01-01", periods=sample_count, freq="s")
    phase_a = np.linspace(0, 8 * np.pi, sample_count)
    phase_b = np.linspace(0, 8.2 * np.pi, sample_count)
    channel_a = np.sin(phase_a) + rng.normal(0, 0.07, sample_count)
    channel_b = 0.999 * np.sin(phase_b + 0.25) + rng.normal(0, 0.05, sample_count)
    enabled = np.zeros(sample_count, dtype=bool)
    enabled[60:150] = True
    enabled[235:335] = True
    enabled[440:560] = True

    return TtsDataFrame(
        {
            "scet": np.tile(times, 3),
            "name": (
                (["channel_a"] * sample_count)
                + (["enabled"] * sample_count)
                + (["channel_b"] * sample_count)
            ),
            "value": np.concatenate([channel_a, enabled, channel_b]),
            "unit": (
                (["volts"] * sample_count)
                + (["bool"] * sample_count)
                + (["volts"] * sample_count)
            ),
        }
    )


def make_plot(data, channels, title, output_path):
    figure, _, _, _ = make_stacked_graph(
        data=data,
        y_vars=[[channel] for channel in channels],
        x_var="scet",
        figure_title=title,
        figure_width=1650,
        figure_height=660,
        plot_lines=True,
        doy=False,
    )
    figure.write_html(output_path, include_plotlyjs="cdn")
    return figure


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    telemetry = make_telemetry()

    filtered_a = telemetry.at_times_where("enabled == 1").filter_expr(
        "name == 'channel_a'"
    ).copy()
    filtered_a["name"] = "filtered_channel_a"
    filtered_a["unit"] = "volts"

    plot_1_data = pd.concat([telemetry, filtered_a], ignore_index=True)
    plot_1_channels = ["channel_a", "enabled", "filtered_channel_a"]

    derived = telemetry.derive_values("difference = channel_a - channel_b")
    plot_2_data = pd.concat(
        [telemetry.filter_expr("name != 'enabled'"), derived], ignore_index=True
    )
    plot_2_channels = ["channel_a", "channel_b", "difference"]

    make_plot(
        plot_1_data,
        plot_1_channels,
        "Channel filtering: A, B, and A while B is true",
        OUTPUT_DIR / "01_filtering_three_subplots.html",
    )
    make_plot(
        plot_2_data,
        plot_2_channels,
        "Channel derivation: A - B reveals the subtle mismatch",
        OUTPUT_DIR / "02_derivation_three_subplots.html",
    )

    print(f"Raw telemetry rows: {len(telemetry)}")
    print(f"Filtered channel A rows: {len(filtered_a)}")
    print(f"Derived difference rows: {len(derived)}")
    print(f"Wrote plots to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
