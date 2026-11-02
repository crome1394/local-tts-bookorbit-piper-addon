# voices

Drop Piper voices here. The server reads this folder, including subfolders, the next time it starts.

The files come from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main). Ryan is at [en/en_US/ryan](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ryan). Download a quality folder and keep the layout, or copy the two files into any subdirectory:

```text
voices/en/en_US/ryan/high/en_US-ryan-high.onnx
voices/en/en_US/ryan/high/en_US-ryan-high.onnx.json
```

Both files are required, and the names have to match (`en_US-ryan-high`, not `model.onnx`). A voice's license stays with that voice. Ryan high is CC BY-NC-SA 4.0, so it is not part of this package. Restart the server after adding a voice.
