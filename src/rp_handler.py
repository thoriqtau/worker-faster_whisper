"""
rp_handler.py for runpod worker

Streaming handler: yields progress events per faster-whisper segment so
clients can poll GET /stream/{job_id} for real-time transcription position.
With return_aggregate_stream enabled, the full event list is also available
via /run and /runsync; the last event is {"type": "result", "output": ...}
where output keeps the exact same shape as the previous blocking worker.
"""

import base64
import json
import sys
import tempfile

import runpod
from runpod.serverless.utils import download_files_from_urls, rp_cleanup
from runpod.serverless.utils.rp_validator import validate

import predict
from rp_schema import INPUT_VALIDATIONS

MODEL = predict.Predictor()
MODEL.setup()


def base64_to_tempfile(base64_file: str) -> str:
    """
    Convert base64 file to tempfile.

    Parameters:
    base64_file (str): Base64 file

    Returns:
    str: Path to tempfile
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(base64.b64decode(base64_file))

    return temp_file.name


def run_whisper_job(job):
    """
    Run inference on the model, yielding streaming events.

    NOTE: This must stay a generator function (no decorators that wrap it).
    The RunPod SDK detects streaming handlers via inspect.isgeneratorfunction;
    wrapping it would silently disable streaming.

    Parameters:
    job (dict): Input job containing the model parameters

    Yields:
    dict: Event with a "type" key: status | progress | result
          (or {"error": ...} for validation failures, which the SDK
          converts into a FAILED job)
    """
    job_input = job["input"]

    input_validation = validate(job_input, INPUT_VALIDATIONS)

    if "errors" in input_validation:
        yield {"error": input_validation["errors"]}
        return
    job_input = input_validation["validated_input"]

    if not job_input.get("audio", False) and not job_input.get("audio_base64", False):
        raise ValueError("Must provide either audio or audio_base64")

    if job_input.get("audio", False) and job_input.get("audio_base64", False):
        raise ValueError("Must provide either audio or audio_base64, not both")

    if job_input.get("audio", False):
        audio_input = download_files_from_urls(job["id"], [job_input["audio"]])[0]

    if job_input.get("audio_base64", False):
        audio_input = base64_to_tempfile(job_input["audio_base64"])

    yield from MODEL.predict_streaming(
        audio=audio_input,
        model_name=job_input["model"],
        transcription=job_input["transcription"],
        translation=job_input["translation"],
        translate=job_input["translate"],
        language=job_input["language"],
        temperature=job_input["temperature"],
        best_of=job_input["best_of"],
        beam_size=job_input["beam_size"],
        patience=job_input["patience"],
        length_penalty=job_input["length_penalty"],
        suppress_tokens=job_input.get("suppress_tokens", "-1"),
        initial_prompt=job_input["initial_prompt"],
        condition_on_previous_text=job_input["condition_on_previous_text"],
        temperature_increment_on_fallback=job_input[
            "temperature_increment_on_fallback"
        ],
        compression_ratio_threshold=job_input["compression_ratio_threshold"],
        logprob_threshold=job_input["logprob_threshold"],
        no_speech_threshold=job_input["no_speech_threshold"],
        enable_vad=job_input["enable_vad"],
        word_timestamps=job_input["word_timestamps"],
    )

    rp_cleanup.clean(["input_objects"])


def _run_local_test(test_input):
    """
    Local test runner for the streaming handler.

    The RunPod SDK's --test_input path does not iterate generator handlers,
    so we drive the generator directly and print each event as a JSON line
    to see progress in real time:

    python rp_handler.py --test_input '{"input": {"audio": "<url>", "model": "base", "transcription": "srt"}}'
    """
    job = dict(test_input)
    job.setdefault("id", "local_test")

    for event in run_whisper_job(job):
        print(json.dumps(event, ensure_ascii=False), flush=True)


if __name__ == "__main__" and "--test_input" in sys.argv:
    # Local test mode: must be checked BEFORE runpod.serverless.start(),
    # because start() parses sys.argv itself and would intercept --test_input
    # (its local runner does not iterate generator handlers).
    _parser_index = sys.argv.index("--test_input")
    if _parser_index + 1 >= len(sys.argv):
        print("Usage: python rp_handler.py --test_input '<json>'", file=sys.stderr)
        sys.exit(1)
    _run_local_test(json.loads(sys.argv[_parser_index + 1]))
    sys.exit(0)


runpod.serverless.start(
    {
        "handler": run_whisper_job,
        "return_aggregate_stream": True,
    }
)
