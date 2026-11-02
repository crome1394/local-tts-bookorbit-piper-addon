# Voices

`./run.sh` sets `BOOKORBIT_TTS_VOICES_DIR` to the `voices/` directory beside it, and creates that directory if it is missing. On startup the server also scans `data/voices`. When the same voice id is in both, the drop directory wins. There is no reload route. Restart after adding a file.

Download voices from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main). Ryan is at [en/en_US/ryan](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ryan). A quality folder already has the two files the server wants. You can also copy the pair into any subdirectory:

```text
voices/en/en_US/ryan/high/en_US-ryan-high.onnx
voices/en/en_US/ryan/high/en_US-ryan-high.onnx.json
```

Both files are required, and the stems have to match. The id has to look like `en_US-ryan-high`: a language, a region, a name, then `x_low`, `low`, `medium`, or `high`. A file whose name is not that shape is skipped. A symlink whose target resolves outside the scanned directory is skipped. Scanning stops after 64 voices.

[docker-compose.example.yml](../docker-compose.example.yml) mounts `./data`, not `./voices`. For that container, put the pair in `./data/voices`.

The [Ryan high model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ryan/high/MODEL_CARD) says the dataset is CC BY-NC-SA 4.0, so those files are not in this package. The tarball ships `en_US-joe-medium`, whose [model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/joe/medium/MODEL_CARD) says CC0. Read the `MODEL_CARD` next to any other voice before you redistribute it.
