![Faster Whisper Logo](https://5ccaof7hvfzuzf4p.public.blob.vercel-storage.com/banner-pjbGKw0buxbWGhMVC165Gf9qgqWo7I.jpeg)

[Faster Whisper](https://github.com/guillaumekln/faster-whisper) is designed to process audio files using various Whisper models, with options for transcription formatting, language translation and more.

---

[![RunPod](https://api.runpod.io/badge/runpod-workers/worker-faster_whisper)](https://www.runpod.io/console/hub/runpod-workers/worker-faster_whisper)

---

## Models

- tiny
- base
- small
- medium
- large-v1
- large-v2
- large-v3
- distil-large-v2
- distil-large-v3
- turbo

## Input

| Input                               | Type  | Description                                                                                                                                                            |
| ----------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `audio`                             | Path  | URL to Audio file                                                                                                                                                      |
| `audio_base64`                      | str   | Base64-encoded audio file                                                                                                                                              |
| `model`                             | str   | Choose a Whisper model. Choices: "tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "distil-large-v2", "distil-large-v3", "turbo". Default: "base" |
| `transcription`                     | str   | Choose the format for the transcription. Choices: "plain_text", "formatted_text", "srt", "vtt". Default: "plain_text"                                                  |
| `translate`                         | bool  | Translate the text to English when set to True. Default: False                                                                                                         |
| `translation`                       | str   | Choose the format for the translation. Choices: "plain_text", "formatted_text", "srt", "vtt". Default: "plain_text"                                                    |
| `language`                          | str   | Language spoken in the audio, specify None to perform language detection. Default: None                                                                                |
| `temperature`                       | float | Temperature to use for sampling. Default: 0                                                                                                                            |
| `best_of`                           | int   | Number of candidates when sampling with non-zero temperature. Default: 5                                                                                               |
| `beam_size`                         | int   | Number of beams in beam search, only applicable when temperature is zero. Default: 5                                                                                   |
| `patience`                          | float | Optional patience value to use in beam decoding. Default: None                                                                                                         |
| `length_penalty`                    | float | Optional token length penalty coefficient (alpha). Default: None                                                                                                       |
| `suppress_tokens`                   | str   | Comma-separated list of token ids to suppress during sampling. Default: "-1"                                                                                           |
| `initial_prompt`                    | str   | Optional text to provide as a prompt for the first window. Default: None                                                                                               |
| `condition_on_previous_text`        | bool  | If True, provide the previous output of the model as a prompt for the next window. Default: True                                                                       |
| `temperature_increment_on_fallback` | float | Temperature to increase when falling back when the decoding fails. Default: 0.2                                                                                        |
| `compression_ratio_threshold`       | float | If the gzip compression ratio is higher than this value, treat the decoding as failed. Default: 2.4                                                                    |
| `logprob_threshold`                 | float | If the average log probability is lower than this value, treat the decoding as failed. Default: -1.0                                                                   |
| `no_speech_threshold`               | float | If the probability of the token is higher than this value, consider the segment as silence. Default: 0.6                                                               |
| `enable_vad`                        | bool  | If True, use the voice activity detection (VAD) to filter out parts of the audio without speech. This step is using the Silero VAD model. Default: False               |
| `word_timestamps`                   | bool  | If True, include word timestamps in the output. Default: False                                                                                                         |

### Example

The following inputs can be used for testing the model:

```json
{
  "input": {
    "audio": "https://github.com/runpod-workers/sample-inputs/raw/main/audio/gettysburg.wav",
    "model": "turbo"
  }
}
```

producing an output like this:

```json
{
  "segments": [
    {
      "id": 1,
      "seek": 106,
      "start": 0.11,
      "end": 3.11,
      "text": " Hello and welcome!",
      "tokens": [50364, 25, 7, 287, 50514],
      "temperature": 0.1,
      "avg_logprob": -0.8348079785480325,
      "compression_ratio": 0.5789473684210527,
      "no_speech_prob": 0.1453857421875
    }
  ],
  "detected_language": "en",
  "transcription": "Hello and welcome!",
  "translation": null,
  "device": "cuda",
  "model": "turbo",
  "translation_time": 0.3796223163604736
}
```

## Streaming progress events

The handler is a streaming (generator) handler. It yields events in this order:

| Event | Shape | Description |
| ----- | ----- | ----------- |
| `status` | `{"type": "status", "message": "loading model"}` | Emitted before the model is loaded |
| `status` | `{"type": "status", "message": "transcribing"}` | Emitted before transcription starts |
| `progress` | `{"type": "progress", "transcribed_until": <float seconds>, "duration": <float seconds>}` | Emitted once per faster-whisper segment; `transcribed_until` is the real position in the audio (from `segment.end`), not an estimate |
| `result` | `{"type": "result", "output": <final output>}` | Last event; `output` has the exact same shape as the non-streaming worker above |

### Usage

Submit a job with `POST /run`, then poll `GET /stream/{job_id}` to receive
events as they are produced:

```bash
JOB_ID=$(curl -s -X POST https://api.runpod.ai/v2/$ENDPOINT_ID/run \
  -H "authorization: $RUNPOD_API_KEY" -H "content-type: application/json" \
  -d '{"input": {"audio": "<url>", "model": "base", "transcription": "srt"}}' | jq -r .id)

# poll repeatedly; progress events show transcribed_until increasing
curl -s https://api.runpod.ai/v2/$ENDPOINT_ID/stream/$JOB_ID -H "authorization: $RUNPOD_API_KEY"
```

With `return_aggregate_stream` enabled, `/run` and `/runsync` also return the
complete event list, where the last element contains the final result:

```json
{
  "output": [
    {"type": "status", "message": "loading model"},
    {"type": "status", "message": "transcribing"},
    {"type": "progress", "transcribed_until": 5.0, "duration": 10.0},
    {"type": "progress", "transcribed_until": 10.0, "duration": 10.0},
    {"type": "result", "output": {"segments": [], "detected_language": "en", "duration": 10.0, "transcription": "...", "translation": null, "device": "cuda", "model": "base"}}
  ]
}
```

### Local testing

```bash
python rp_handler.py --test_input '{"input": {"audio": "<url>", "model": "base", "transcription": "srt"}}'
```

Each yielded event is printed as a JSON line in real time.
