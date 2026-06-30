"""
Real-time transition inference from a serial stream or CSV replay.

Run from the project root:

    python analysis/transition_classification/live/live_predict.py --model analysis/transition_classification/models/svm_rbf.joblib --port COM16

Replay a recorded CSV instead of using hardware:

    python analysis/transition_classification/live/live_predict.py --model analysis/transition_classification/models/logistic_regression.joblib --csv datasets/raw/harshit/harshit_session_001_20260626_184217.csv

List available serial ports:

    python analysis/transition_classification/live/live_predict.py --list-ports
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from analysis.transition_classification.live.decision_layer import DecisionResult, PredictionDecisionLayer
from analysis.transition_classification.live.inference_utils import load_model, predict_with_confidence
from analysis.transition_classification.live.preprocessing import SlidingWindowPreprocessor
from analysis.transition_classification.live.serial_stream import format_available_ports, iter_csv_samples, iter_serial_samples
from analysis.transition_classification.live_debug.session_logger import DebugSessionRecorder


def format_confidence(confidence: Optional[float]) -> str:
    if confidence is None:
        return "N/A"
    return f"{confidence * 100:.1f}%"


def print_prediction_block(
    window_id: int,
    timestamp_ms: int,
    raw_prediction: str,
    decision: DecisionResult,
    preprocess_time: float,
    infer_time: float,
) -> None:
    total = preprocess_time + infer_time + decision.decision_seconds
    print("--------------------------------")
    print(f"Window {window_id}")
    print(f"Timestamp : {timestamp_ms}")
    print(f"Raw Prediction : {raw_prediction}")
    print(f"Confidence : {format_confidence(decision.confidence)}")
    print(f"Filtered Prediction : {decision.filtered_prediction or 'N/A'}")
    print(f"Current Stable State : {decision.stable_state or 'N/A'}")
    print(f"Decision : {decision.decision}")
    print(f"Reason : {decision.reason}")
    print(f"Preprocessing time : {preprocess_time * 1000:.2f} ms")
    print(f"Inference time : {infer_time * 1000:.2f} ms")
    print(f"Decision time : {decision.decision_seconds * 1000:.2f} ms")
    print(f"Total latency : {total * 1000:.2f} ms")
    print("--------------------------------\n")


def _create_recorder(
    debug_session: str,
    participant: str,
    session: str,
    sampling_rate: int,
    window_size: float,
    overlap: float,
    model_path: str,
) -> DebugSessionRecorder:
    session_dir = Path(debug_session)
    return DebugSessionRecorder(
        output_dir=session_dir,
        participant=participant,
        session=session,
        sampling_rate=sampling_rate,
        window_size=window_size,
        overlap=overlap,
        model_used=Path(model_path).name,
    )


def print_summary(
    count: int,
    total_latency: float,
    total_preprocess: float,
    total_infer: float,
    decision_layer: PredictionDecisionLayer,
) -> None:
    if not count:
        return
    metrics = decision_layer.metrics
    avg_conf = metrics.average_confidence
    print("Summary")
    print(f"Average latency : {(total_latency / count) * 1000:.2f} ms")
    print(f"Average preprocessing time : {(total_preprocess / count) * 1000:.2f} ms")
    print(f"Average inference time : {(total_infer / count) * 1000:.2f} ms")
    print(f"Average decision latency : {metrics.average_decision_latency * 1000:.2f} ms")
    print(f"Average confidence : {format_confidence(avg_conf)}")
    print(f"Ignored predictions : {metrics.ignored_predictions}")
    print(f"Accepted predictions : {metrics.accepted_predictions}")
    print(f"State changes : {metrics.state_changes}")
    print(f"False state flips prevented : {metrics.false_state_flips_prevented}")


def run_live(
    model_path: str,
    port: Optional[str],
    baud: int,
    window_size: float,
    overlap: float,
    duration: Optional[float] = None,
    recorder: Optional[DebugSessionRecorder] = None,
) -> None:
    model = load_model(model_path)
    preprocessor = SlidingWindowPreprocessor(window_size_seconds=window_size, overlap=overlap)
    decision_layer = PredictionDecisionLayer()
    total_preprocess = 0.0
    total_infer = 0.0
    total_latency = 0.0
    count = 0
    sample_count = 0
    print(f"Loaded model: {model_path}")
    if recorder:
        print(f"Recording debug session to: {recorder.output_dir}")
    if duration is not None:
        print(f"Auto-stop after: {duration:.1f} seconds")
    print("Listening for live samples...\n")

    try:
        start_time = time.perf_counter()
        for sample in iter_serial_samples(port=port, baud=baud):
            if duration is not None and (time.perf_counter() - start_time) >= duration:
                print(f"Stopping after {duration:.1f} seconds.")
                break
            sample_count += 1
            if recorder:
                recorder.record_sample(sample_count - 1, sample)
            windows = preprocessor.add_sample(sample)
            for window in windows:
                features = window.features
                preprocess_time = window.preprocessing_seconds

                t1 = time.perf_counter()
                prediction, confidence = predict_with_confidence(model, features)
                infer_time = time.perf_counter() - t1
                decision = decision_layer.update(prediction, confidence)

                total = preprocess_time + infer_time + decision.decision_seconds
                total_preprocess += preprocess_time
                total_infer += infer_time
                total_latency += total
                count += 1

                if recorder:
                    recorder.record_window(
                        window_id=window.window_id,
                        start_sample=window.start_sample,
                        end_sample=window.end_sample,
                        start_timestamp=window.start_timestamp_ms,
                        end_timestamp=window.end_timestamp_ms,
                        window_size=window.window_size_seconds,
                        overlap=window.overlap,
                        window_size_seconds=window.window_size_seconds,
                        window_size_samples=window.window_size_samples,
                        step_samples=window.step_samples,
                    )
                    recorder.record_features(
                        window_id=window.window_id,
                        start_timestamp=window.start_timestamp_ms,
                        end_timestamp=window.end_timestamp_ms,
                        features=features,
                    )
                    recorder.record_prediction(
                        window_id=window.window_id,
                        prediction=prediction,
                        confidence=decision.confidence,
                        inference_time_ms=infer_time * 1000.0,
                        preprocessing_time_ms=preprocess_time * 1000.0,
                        total_latency_ms=total * 1000.0,
                        decision_time_ms=decision.decision_seconds * 1000.0,
                        filtered_prediction=decision.filtered_prediction,
                        stable_state=decision.stable_state,
                        decision=decision.decision,
                        decision_reason=decision.reason,
                    )

                print_prediction_block(window.window_id, window.end_timestamp_ms, prediction, decision, preprocess_time, infer_time)
    finally:
        print_summary(count, total_latency, total_preprocess, total_infer, decision_layer)
        if recorder:
            recorder.finalize()


def run_replay(
    model_path: str,
    csv_path: Path,
    window_size: float,
    overlap: float,
    duration: Optional[float] = None,
    recorder: Optional[DebugSessionRecorder] = None,
) -> None:
    model = load_model(model_path)
    preprocessor = SlidingWindowPreprocessor(window_size_seconds=window_size, overlap=overlap)
    decision_layer = PredictionDecisionLayer()
    total_preprocess = 0.0
    total_infer = 0.0
    total_latency = 0.0
    count = 0
    sample_count = 0

    print(f"Loaded model: {model_path}")
    print(f"Replaying CSV: {csv_path}")
    if recorder:
        print(f"Recording debug session to: {recorder.output_dir}")
    if duration is not None:
        print(f"Auto-stop after: {duration:.1f} seconds")
    print()

    try:
        start_time = time.perf_counter()
        for sample in iter_csv_samples(csv_path, realtime=True):
            if duration is not None and (time.perf_counter() - start_time) >= duration:
                print(f"Stopping after {duration:.1f} seconds.")
                break
            sample_count += 1
            if recorder:
                recorder.record_sample(sample_count - 1, sample)
            windows = preprocessor.add_sample(sample)
            for window in windows:
                features = window.features
                preprocess_time = window.preprocessing_seconds

                t1 = time.perf_counter()
                prediction, confidence = predict_with_confidence(model, features)
                infer_time = time.perf_counter() - t1
                decision = decision_layer.update(prediction, confidence)

                total = preprocess_time + infer_time + decision.decision_seconds
                total_preprocess += preprocess_time
                total_infer += infer_time
                total_latency += total
                count += 1

                if recorder:
                    recorder.record_window(
                        window_id=window.window_id,
                        start_sample=window.start_sample,
                        end_sample=window.end_sample,
                        start_timestamp=window.start_timestamp_ms,
                        end_timestamp=window.end_timestamp_ms,
                        window_size=window.window_size_seconds,
                        overlap=window.overlap,
                        window_size_seconds=window.window_size_seconds,
                        window_size_samples=window.window_size_samples,
                        step_samples=window.step_samples,
                    )
                    recorder.record_features(
                        window_id=window.window_id,
                        start_timestamp=window.start_timestamp_ms,
                        end_timestamp=window.end_timestamp_ms,
                        features=features,
                    )
                    recorder.record_prediction(
                        window_id=window.window_id,
                        prediction=prediction,
                        confidence=decision.confidence,
                        inference_time_ms=infer_time * 1000.0,
                        preprocessing_time_ms=preprocess_time * 1000.0,
                        total_latency_ms=total * 1000.0,
                        decision_time_ms=decision.decision_seconds * 1000.0,
                        filtered_prediction=decision.filtered_prediction,
                        stable_state=decision.stable_state,
                        decision=decision.decision,
                        decision_reason=decision.reason,
                    )

                print_prediction_block(window.window_id, window.end_timestamp_ms, prediction, decision, preprocess_time, infer_time)
    finally:
        print_summary(count, total_latency, total_preprocess, total_infer, decision_layer)
        if recorder:
            recorder.finalize()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live transition inference")
    parser.add_argument("--model", required=False, help="Path to a saved sklearn/joblib model")
    parser.add_argument("--port", default=None, help="Serial port, for example COM16")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--window-size", type=float, default=2.0, help="Sliding window size in seconds")
    parser.add_argument("--overlap", type=float, default=0.5, help="Sliding window overlap fraction")
    parser.add_argument("--csv", default=None, help="Replay a recorded CSV instead of live serial input")
    parser.add_argument("--debug-session", default=None, help="Write a full debug session bundle to this directory")
    parser.add_argument("--participant", default="unknown", help="Participant identifier for debug metadata")
    parser.add_argument("--session-id", default="unknown", help="Session identifier for debug metadata")
    parser.add_argument("--sampling-rate", type=int, default=50, help="Sampling rate to record in debug metadata")
    parser.add_argument("--duration", type=float, default=None, help="Optional auto-stop duration in seconds")
    parser.add_argument("--list-ports", action="store_true", help="List visible serial ports and exit")
    args = parser.parse_args()

    if args.list_ports:
        print(format_available_ports())
        return

    if not args.model:
        raise SystemExit("--model is required unless you use --list-ports")

    recorder = None
    if args.debug_session:
        recorder = _create_recorder(
            args.debug_session,
            participant=args.participant,
            session=args.session_id,
            sampling_rate=args.sampling_rate,
            window_size=args.window_size,
            overlap=args.overlap,
            model_path=args.model,
        )

    if args.csv:
        run_replay(args.model, Path(args.csv), args.window_size, args.overlap, duration=args.duration, recorder=recorder)
    else:
        run_live(args.model, args.port, args.baud, args.window_size, args.overlap, duration=args.duration, recorder=recorder)


if __name__ == "__main__":
    main()
