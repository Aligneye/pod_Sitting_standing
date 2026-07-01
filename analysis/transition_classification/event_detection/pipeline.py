"""Coordinator for event extraction with staged validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from analysis.transition_classification.event_detection.config import DEFAULT_CONFIG, EventDetectionConfig
from analysis.transition_classification.event_detection.context_window import ContextWindowBuilder, TransitionWindow
from analysis.transition_classification.event_detection.event_summary import build_event_summary, transition_window_to_dataframe
from analysis.transition_classification.event_detection.movement_detector import MovementDetector
from analysis.transition_classification.event_detection.orientation_validator import (
    OrientationValidationResult,
    OrientationValidationStatus,
    OrientationValidator,
    StageResult,
    ValidationStage,
)
from analysis.transition_classification.event_detection.transition_extractor import TransitionExtractor
from analysis.transition_classification.live.serial_stream import Sample


class EventDebugWriter:
    """Write completed transition windows for visual validation."""

    def __init__(self, output_dir: str | Path, config: EventDetectionConfig = DEFAULT_CONFIG) -> None:
        self.output_dir = Path(output_dir)
        self.config = config
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        window: TransitionWindow,
        sampling_rate_hz: int,
        validation: OrientationValidationResult | None = None,
    ) -> Path:
        """Write CSV, metadata, and Plotly HTML for one completed event."""
        event_dir = self.output_dir / f"event_{window.event_id:04d}"
        event_dir.mkdir(parents=True, exist_ok=True)

        df = transition_window_to_dataframe(window)
        df.to_csv(event_dir / "raw_samples.csv", index=False)
        (event_dir / "metadata.json").write_text(
            json.dumps(self._metadata(window, validation), indent=2),
            encoding="utf-8",
        )
        summary = build_event_summary(window, sampling_rate_hz)
        if validation is not None:
            summary["validation"] = self._validation_summary(validation)
        (event_dir / "event_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        self._write_plot(window, df, event_dir / "event_plot.html", validation)
        if validation is not None:
            self._write_statistical_plots(validation, event_dir)
        return event_dir

    def _metadata(
        self,
        window: TransitionWindow,
        validation: OrientationValidationResult | None,
    ) -> dict:
        payload = {
            "event_id": window.event_id,
            "movement_start_index": window.movement_start_index,
            "movement_end_index": window.movement_end_index,
            "movement_start_sample_index": window.movement_start_sample_index,
            "movement_end_sample_index": window.movement_end_sample_index,
            "movement_start_timestamp_ms": window.movement_start_timestamp_ms,
            "movement_end_timestamp_ms": window.movement_end_timestamp_ms,
            "debounce_merges": window.debounce_merges,
            "pre_context_samples": window.pre_context_samples,
            "post_context_samples": window.post_context_samples,
            "total_samples": window.total_samples,
            "duration_ms": window.duration_ms,
            "raw_samples_csv": "raw_samples.csv",
            "plotly_html": "event_plot.html",
            "event_summary_json": "event_summary.json",
            "mean_plot_html": "mean_comparison.html",
            "std_plot_html": "std_comparison.html",
            "variance_plot_html": "variance_comparison.html",
            "delta_mean_plot_html": "delta_mean.html",
            "stage_breakdown_plot_html": "stage_breakdown.html",
            "combined_std_plot_html": "combined_std_analysis.html",
        }
        if validation is not None:
            payload["validation"] = self._validation_summary(validation)
        return payload

    def _validation_summary(self, validation: OrientationValidationResult) -> dict:
        stage_summaries = {}
        for name, result in validation.stage_results.items():
            stage_summaries[name] = {
                "passed": result.passed,
                "reason": result.reason,
                "metrics": result.metrics,
            }

        sd = validation.stability_diagnostics
        return {
            "status": validation.status.value,
            "is_valid": validation.is_valid,
            "reason": validation.reason,
            "validation_pipeline_version": validation.validation_pipeline_version,
            "validation_stage_passed": validation.validation_stage_passed,
            "validation_stage_failed": validation.validation_stage_failed,
            "rejection_stage": validation.rejection_stage,
            "stages": stage_summaries,
            "rolling_std_metrics": validation.rolling_std_metrics,
            "stability_diagnostics": {
                "note": "Diagnostic only — does not reject events.",
                "combined_std_pre": sd.pre_std,
                "combined_std_post": sd.post_std,
                "combined_std_transition": sd.transition_std,
                "stable_average_std": sd.stable_average_std,
                "transition_to_stable_ratio": sd.transition_to_stable_ratio,
            },
            "thresholds": validation.thresholds,
            "legacy_orientation_metrics": {
                "disabled_reason": "Intentionally disabled — overly sensitive during experimentation.",
                "mean_before": validation.legacy_orientation_metrics.mean_before,
                "mean_after": validation.legacy_orientation_metrics.mean_after,
                "delta_x": validation.legacy_orientation_metrics.delta_x,
                "delta_y": validation.legacy_orientation_metrics.delta_y,
                "delta_z": validation.legacy_orientation_metrics.delta_z,
                "gravity_magnitude_before": validation.legacy_orientation_metrics.gravity_magnitude_before,
                "gravity_magnitude_after": validation.legacy_orientation_metrics.gravity_magnitude_after,
                "gravity_magnitude_change": validation.legacy_orientation_metrics.gravity_magnitude_change,
                "angle_change_deg": validation.legacy_orientation_metrics.angle_change_deg,
                "stability_before": validation.legacy_orientation_metrics.stability_before,
                "stability_after": validation.legacy_orientation_metrics.stability_after,
            },
        }

    # ------------------------------------------------------------------
    # Main event plot
    # ------------------------------------------------------------------

    def _write_plot(
        self,
        window: TransitionWindow,
        df: pd.DataFrame,
        output_path: Path,
        validation: OrientationValidationResult | None,
    ) -> None:
        if df.empty:
            return

        fig = go.Figure()
        axis_styles = {
            "acc_x": "#d62728",
            "acc_y": "#2ca02c",
            "acc_z": "#1f77b4",
        }
        for axis, color in axis_styles.items():
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp_ms"],
                    y=df[axis],
                    mode="lines",
                    name=axis,
                    line={"width": 2, "color": color},
                )
            )
        fig.add_trace(
            go.Scatter(
                x=df["timestamp_ms"],
                y=df["gravity_magnitude"],
                mode="lines",
                name="gravity_magnitude",
                line={"width": 2, "dash": "dot", "color": "#111111"},
            )
        )

        rolling = self._rolling_combined_std(df)
        fig.add_trace(
            go.Scatter(
                x=df["timestamp_ms"],
                y=rolling,
                mode="lines",
                name="rolling_combined_std",
                line={"width": 3, "color": "#f39c12"},
                yaxis="y2",
            )
        )

        start_ts = int(df.iloc[window.movement_start_index]["timestamp_ms"])
        end_ts = int(df.iloc[window.movement_end_index]["timestamp_ms"])
        first_ts = int(df.iloc[0]["timestamp_ms"])
        last_ts = int(df.iloc[-1]["timestamp_ms"])

        fig.add_vrect(
            x0=first_ts,
            x1=start_ts,
            fillcolor="rgba(52, 152, 219, 0.14)",
            line_width=0,
            annotation_text="PRE CONTEXT",
            annotation_position="top left",
        )
        debounce_ms = self.config.transition_end_debounce_ms
        debounce_start_ts = max(start_ts, end_ts - debounce_ms)

        fig.add_vrect(
            x0=start_ts,
            x1=debounce_start_ts,
            fillcolor="rgba(231, 76, 60, 0.16)",
            line_width=0,
            annotation_text="TRANSITION",
            annotation_position="top left",
        )
        fig.add_vrect(
            x0=debounce_start_ts,
            x1=end_ts,
            fillcolor="rgba(155, 89, 182, 0.18)",
            line_width=0,
            annotation_text="POSSIBLE END / DEBOUNCE",
            annotation_position="top left",
        )
        fig.add_vrect(
            x0=end_ts,
            x1=last_ts,
            fillcolor="rgba(46, 204, 113, 0.14)",
            line_width=0,
            annotation_text="POST CONTEXT",
            annotation_position="top left",
        )

        fig.add_vline(
            x=start_ts, line_color="#c0392b", line_dash="dash", line_width=3,
            annotation_text="movement start",
            annotation_position="top right",
        )
        fig.add_vline(
            x=end_ts, line_color="#27ae60", line_dash="dash", line_width=3,
            annotation_text="movement end",
            annotation_position="top right",
        )

        cooldown_start = last_ts
        cooldown_end = last_ts + self.config.event_cooldown_ms
        fig.add_vrect(
            x0=cooldown_start,
            x1=cooldown_end,
            fillcolor="rgba(241, 196, 15, 0.15)",
            line_width=0,
            annotation_text="COOLDOWN",
            annotation_position="top right",
        )

        threshold = self.config.rolling_combined_std_threshold
        fig.add_hline(
            y=threshold, line_color="#f39c12", line_dash="dot", yref="y2",
            annotation_text=f"rolling STD threshold ({threshold})",
            annotation_position="top right",
        )
        self._add_rolling_std_candidate_regions(fig, df, rolling)

        title = self._build_plot_title(window, validation)
        fig.update_layout(
            title=title,
            xaxis_title="timestamp_ms",
            yaxis_title="acceleration",
            yaxis2={
                "title": "rolling_combined_std",
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
            },
            hovermode="x unified",
            template="plotly_white",
            legend={"orientation": "h", "y": 1.08},
        )
        fig.write_html(output_path)

    def _build_plot_title(
        self,
        window: TransitionWindow,
        validation: OrientationValidationResult | None,
    ) -> str:
        if validation is None:
            return f"Detected Transition Event {window.event_id}"

        status_label = validation.status.value
        stage_lines = []
        for stage_name in [ValidationStage.MOVEMENT.value, ValidationStage.ORIENTATION.value]:
            if stage_name in validation.stage_results:
                result = validation.stage_results[stage_name]
                mark = "✓" if result.passed else "✗"
                stage_lines.append(f"{stage_name.capitalize()} {mark}")
            else:
                stage_lines.append(f"{stage_name.capitalize()} — not evaluated")

        stages_str = " | ".join(stage_lines)
        return f"{status_label} | Event {window.event_id} | {stages_str}"

    # ------------------------------------------------------------------
    # Statistical/diagnostic plots
    # ------------------------------------------------------------------

    def _write_statistical_plots(self, validation: OrientationValidationResult, event_dir: Path) -> None:
        features = validation.statistical_features
        self._write_region_bar_plot(
            features,
            stat_name="mean",
            title="Mean Comparison by Region",
            output_path=event_dir / "mean_comparison.html",
        )
        self._write_region_bar_plot(
            features,
            stat_name="standard_deviation",
            title="STD Comparison by Region",
            output_path=event_dir / "std_comparison.html",
        )
        self._write_region_bar_plot(
            features,
            stat_name="variance",
            title="Variance Comparison by Region",
            output_path=event_dir / "variance_comparison.html",
        )
        self._write_delta_mean_plot(features, event_dir / "delta_mean.html")
        self._write_stage_breakdown_plot(validation, event_dir / "stage_breakdown.html")
        self._write_combined_std_plot(features, event_dir / "combined_std_analysis.html")

    def _write_region_bar_plot(self, features: dict, stat_name: str, title: str, output_path: Path) -> None:
        rows = []
        for region_key, region_label in [
            ("pre_context", "PRE"),
            ("transition", "TRANSITION"),
            ("post_context", "POST"),
        ]:
            values = features["regions"][region_key][stat_name]
            for axis, value in values.items():
                rows.append({"region": region_label, "axis": axis, "value": value})
        df = pd.DataFrame(rows)
        fig = go.Figure()
        for axis in ["acc_x", "acc_y", "acc_z"]:
            axis_df = df[df["axis"] == axis]
            fig.add_trace(go.Bar(x=axis_df["region"], y=axis_df["value"], name=axis))
        fig.update_layout(title=title, xaxis_title="Region", yaxis_title=stat_name, barmode="group", template="plotly_white")
        fig.write_html(output_path)

    def _write_delta_mean_plot(self, features: dict, output_path: Path) -> None:
        delta = features["delta_features"]
        labels = ["delta_mean_x", "delta_mean_y", "delta_mean_z"]
        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=[delta[label] for label in labels],
                    marker_color=["#d62728", "#2ca02c", "#1f77b4"],
                )
            ]
        )
        fig.update_layout(title="Delta Mean: POST - PRE", xaxis_title="Feature", yaxis_title="Delta", template="plotly_white")
        fig.write_html(output_path)

    def _write_stage_breakdown_plot(self, validation: OrientationValidationResult, output_path: Path) -> None:
        """Show each validation stage as pass/fail with key metric values."""
        stage_order = [ValidationStage.MOVEMENT.value, ValidationStage.ORIENTATION.value]
        labels = []
        passed_values = []
        colors = []
        hover_texts = []

        for stage_name in stage_order:
            if stage_name in validation.stage_results:
                result = validation.stage_results[stage_name]
                labels.append(stage_name.capitalize())
                passed_values.append(1 if result.passed else 0)
                colors.append("#27ae60" if result.passed else "#c0392b")
                hover_texts.append(result.reason)
            else:
                labels.append(stage_name.capitalize())
                passed_values.append(0)
                colors.append("#95a5a6")
                hover_texts.append("Not evaluated")

        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=passed_values,
                    text=hover_texts,
                    hoverinfo="text",
                    marker_color=colors,
                )
            ]
        )

        status_text = "VALID" if validation.is_valid else "REJECTED"
        if validation.rejection_stage:
            status_text += f" at {validation.rejection_stage}"

        fig.update_layout(
            title=f"Staged Validation: {status_text}",
            xaxis_title="Stage",
            yaxis_title="Pass (1) / Fail (0)",
            yaxis={"dtick": 1, "range": [0, 1.2]},
            template="plotly_white",
        )
        fig.write_html(output_path)

    def _write_combined_std_plot(self, features: dict, output_path: Path) -> None:
        combined = features["combined_std"]
        ratios = features["relative_std_metrics"]
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=["PRE", "TRANSITION", "POST"],
                y=[combined["pre"], combined["transition"], combined["post"]],
                name="Combined STD",
                marker_color=["#3498db", "#e74c3c", "#2ecc71"],
            )
        )
        ratio_labels = ["Transition / Pre", "Transition / Post", "Transition / Stable Avg"]
        ratio_values = [
            ratios["transition_vs_pre"],
            ratios["transition_vs_post"],
            ratios["transition_vs_average_stable"],
        ]
        fig.add_trace(
            go.Bar(
                x=ratio_labels,
                y=ratio_values,
                name="Relative STD Ratio",
                marker_color="#f39c12",
                yaxis="y2",
            )
        )
        fig.update_layout(
            title="Combined Standard Deviation Analysis",
            xaxis_title="Metric",
            yaxis={"title": "Combined STD"},
            yaxis2={"title": "Ratio", "overlaying": "y", "side": "right", "showgrid": False},
            barmode="group",
            template="plotly_white",
        )
        fig.write_html(output_path)

    # ------------------------------------------------------------------
    # Rolling STD helpers
    # ------------------------------------------------------------------

    def _rolling_combined_std(self, df: pd.DataFrame) -> pd.Series:
        window = max(2, int(self.config.rolling_std_window_samples))
        rolling_x = df["acc_x"].rolling(window=window, min_periods=2).std(ddof=0).fillna(0.0)
        rolling_y = df["acc_y"].rolling(window=window, min_periods=2).std(ddof=0).fillna(0.0)
        rolling_z = df["acc_z"].rolling(window=window, min_periods=2).std(ddof=0).fillna(0.0)
        return ((rolling_x ** 2) + (rolling_y ** 2) + (rolling_z ** 2)).pow(0.5)

    def _add_rolling_std_candidate_regions(self, fig: go.Figure, df: pd.DataFrame, rolling: pd.Series) -> None:
        threshold = self.config.rolling_combined_std_threshold
        active = rolling > threshold
        if not active.any():
            return

        start_idx = None
        for idx, is_active in enumerate(active.tolist()):
            if is_active and start_idx is None:
                start_idx = idx
            elif not is_active and start_idx is not None:
                self._add_candidate_region(fig, df, start_idx, idx - 1)
                start_idx = None
        if start_idx is not None:
            self._add_candidate_region(fig, df, start_idx, len(df) - 1)

    def _add_candidate_region(self, fig: go.Figure, df: pd.DataFrame, start_idx: int, end_idx: int) -> None:
        fig.add_vrect(
            x0=int(df.iloc[start_idx]["timestamp_ms"]),
            x1=int(df.iloc[end_idx]["timestamp_ms"]),
            fillcolor="rgba(243, 156, 18, 0.10)",
            line_width=0,
            annotation_text="rolling STD above threshold",
            annotation_position="bottom left",
        )


class EventDetectionPipeline:
    """Process samples one at a time and emit completed TransitionWindow events."""

    def __init__(
        self,
        movement_detector: Optional[MovementDetector] = None,
        transition_extractor: Optional[TransitionExtractor] = None,
        context_window_builder: Optional[ContextWindowBuilder] = None,
        orientation_validator: Optional[OrientationValidator] = None,
        debug_writer: Optional[EventDebugWriter] = None,
        rejected_debug_writer: Optional[EventDebugWriter] = None,
        config: EventDetectionConfig = DEFAULT_CONFIG,
    ) -> None:
        self.config = config
        self.movement_detector = movement_detector or MovementDetector(config)
        self.transition_extractor = transition_extractor or TransitionExtractor(config)
        self.context_window_builder = context_window_builder or ContextWindowBuilder(config)
        self.orientation_validator = orientation_validator or OrientationValidator(config)
        self.debug_writer = debug_writer or EventDebugWriter(config.debug_events_dir, config)
        self.rejected_debug_writer = rejected_debug_writer or EventDebugWriter(config.debug_rejected_events_dir, config)
        self._cooldown_until_ms: int = 0

    @property
    def in_cooldown(self) -> bool:
        return self._cooldown_until_ms > 0

    def process_sample(self, sample: Sample) -> TransitionWindow | None:
        """Process one sample and return a completed transition window if ready.

        During cooldown, samples are consumed but no new events are started.
        """
        if self._cooldown_until_ms > 0 and sample.timestamp_ms < self._cooldown_until_ms:
            return None

        if self._cooldown_until_ms > 0 and sample.timestamp_ms >= self._cooldown_until_ms:
            self._cooldown_until_ms = 0

        movement = self.movement_detector.update(sample)
        completed_segment = self.transition_extractor.update(sample, movement)
        window = self.context_window_builder.update(sample, movement, completed_segment)
        if window is not None:
            validation = self.orientation_validator.validate(window)
            if validation.status == OrientationValidationStatus.VALID_TRANSITION:
                self._enter_cooldown(window)
                if self.debug_writer is not None:
                    self.debug_writer.write(window, self.config.sampling_rate_hz, validation)
            elif self.rejected_debug_writer is not None:
                self.rejected_debug_writer.write(window, self.config.sampling_rate_hz, validation)
        return window

    def _enter_cooldown(self, window: TransitionWindow) -> None:
        """Start the refractory period after a valid transition."""
        event_end_ms = window.samples[-1].timestamp_ms if window.samples else 0
        self._cooldown_until_ms = int(event_end_ms) + self.config.event_cooldown_ms
