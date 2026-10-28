# 扎提维语 skill · Uyghur Local Voice

在 Apple Silicon Mac 上，用已授权的参考音色生成维语配音。基于 [OmniVoice](https://github.com/k2-fsa/OmniVoice)，提供本地中文操作面板和 Codex skill。

- 维文输入、从右向左排版，固定使用 `ug` 语言。
- 保存和选择多个音色，生成后试听、下载 WAV、查看历史作品。
- 首次安装和下载模型需要联网，配音默认离线运行。
- 录音、文稿、模型与成品存放在本机私人目录，不随代码发布。

**当前为试用版。** 已在 Apple M2 / 16 GB 上完成约 7 秒声音克隆测试。发音准确度和音色相似度仍需试听检查；新机器安装流程尚未独立验证。本项目发布在 GitHub，配音服务运行在用户自己的 Mac，不是在线托管网站。

## 安装

需要 Apple Silicon macOS、Git、[uv](https://docs.astral.sh/uv/)。本项目不包含任何人的音色或模型权重。

```sh
git clone https://github.com/Alzat007/uyghur-local-voice.git "$HOME/.codex/skills/uyghur-local-voice"
voice_skill="$HOME/.codex/skills/uyghur-local-voice"
voice_data="$HOME/Library/Application Support/uyghur-voice-lab"
mkdir -p "$voice_data"
uv venv --python 3.11 "$voice_data/.venv"
uv pip install --python "$voice_data/.venv/bin/python" -r "$voice_skill/requirements.txt"
```

如果技能、虚拟环境或模型已存在，直接复用，不必重新安装。TTS 主模型和音频 tokenizer 共约 3.26 GB；另需 Python 依赖空间。

下载 TTS 模型到私人目录：

```sh
"$voice_data/.venv/bin/python" - "$voice_data" <<'PY'
from pathlib import Path
import sys
from huggingface_hub import snapshot_download
snapshot_download('k2-fsa/OmniVoice', local_dir=Path(sys.argv[1]) / 'models/OmniVoice')
PY
```

使用前请阅读下方的模型许可。

## 保存音色

准备 3–10 秒清晰的单人维语 WAV，以及与声音完全对应的 UTF-8 逐字稿。请使用本人或已获授权的声音。下面的路径和授权说明应替换为实际内容。

```sh
"$voice_data/.venv/bin/python" "$voice_skill/scripts/voices.py" add \
  --id my-voice --name '我的维语音色' \
  --audio '/absolute/path/reference.wav' \
  --transcript '/absolute/path/transcript.txt' \
  --authorization '录音为本人声音，允许用于声音克隆' \
  --transcript-status human_verified
```

已有本项目旧试用数据时，可运行 `python3 "$voice_skill/scripts/voices.py" import-trial`。这只读取本机保存的授权记录，不附赠音色。

没有逐字稿时可使用可选 ASR：按上面的下载方式将 `aadel4/omniASR-CTC-300M-v2` 下载到 `models/OmniASR-CTC-300M-v2`（约 1.30 GB），然后运行 `transcribe.py --audio <音频> --output <新稿件.txt>`。机器稿不等于人工核对，试用流程见 [工作流说明](references/workflow.md)。

## 打开面板

```sh
python3 "$voice_skill/scripts/launch.py" --open
```

或双击 `打开维语配音.command`。默认地址为 `http://127.0.0.1:8767`。输入维文、选择音色，然后生成。单次最多 2000 字符，建议先用 1–3 句话试听。仅支持本机访问，不安装登录启动项。生成任务完成后可关闭页面，成品仍保存在磁盘。

在 Codex 中可说：**“用扎提维语 skill，把这段维文生成配音。”** 调用标识为 `$uyghur-local-voice`，具体操作约定见 [SKILL.md](SKILL.md)。

直接生成 WAV：

```sh
"$voice_data/.venv/bin/python" "$voice_skill/scripts/synthesize.py" \
  --text-file '/absolute/path/script.txt' --voice my-voice
```

省略输出路径时自动保存到私人目录的 `outputs/`，不会覆盖已有作品。所有脚本支持 `--data-dir`，也可设置 `UYGHUR_VOICE_DATA_DIR`。

## 数据与运行限制

默认私人目录为 `~/Library/Application Support/uyghur-voice-lab`：

| 目录或文件 | 用途 |
| --- | --- |
| `.venv/`、`models/` | Python 环境、模型 |
| `voices.json`、`voices/`、`references/` | 私人音色、授权、参考资料 |
| `outputs/` | WAV 配音及元数据 |
| `jobs/`、`logs/` | 文稿、任务状态和日志 |

一次运行一个推理任务；面板任务超过 20 分钟会停止。MPS 不可用时回退 CPU，速度可能较慢。模型 tokenizer 使用 CPU；ASR 固定 CPU。不要导入来源不明的 `.pt` 声音提示。不要将私人数据目录提交到 Git。

## 许可与来源

本项目自身代码为 [MIT](LICENSE)。依赖和模型遵守各自许可证；MIT 不会改变模型权重的使用限制。

- [OmniVoice 源码](https://github.com/k2-fsa/OmniVoice)：Apache-2.0。
- [OmniVoice 预训练权重](https://huggingface.co/k2-fsa/OmniVoice#license)：CC-BY-NC，商业用途应另行核实许可或更换适合的模型。
- [可选 ASR 模型](https://huggingface.co/aadel4/omniASR-CTC-300M-v2)：使用前查看其模型卡和许可。

原版中文配音工具：[扎提skill / macos-local-voice](https://github.com/Alzat007/macos-local-voice)。两个项目使用不同后端，数据与运行环境相互独立。
