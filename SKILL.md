---
name: uyghur-local-voice
description: "扎提维语 skill：在 Apple Silicon Mac 本地用 OmniVoice 保存已授权音色、克隆维语声音并生成维语配音。用于维文转语音、复用音色、打开维语配音面板及参考录音机器转写。"
---

# 扎提维语 skill

使用 OmniVoice 的 `ug` 语言生成维语。面板支持维文从右向左输入、音色选择、异步生成、试听、WAV 下载与最近 50 条作品。

## 日常使用

解析本技能目录为 `<skill>`。默认私人目录 `<data>` 为 `~/Library/Application Support/uyghur-voice-lab`；脚本支持 `--data-dir` 或环境变量 `UYGHUR_VOICE_DATA_DIR`。录音、文稿、模型、虚拟环境与输出保存在私人目录，不能包含在技能分享包中。

1. 执行 `python3 <skill>/scripts/voices.py status`。复用已有模型。若存在旧的 `project-status.json` 但尚未导入音色，运行 `voices.py import-trial`，沿用原授权和机器稿试用状态。
2. 打开面板：`python3 <skill>/scripts/launch.py`，用应用浏览器打开返回的本机地址。双击技能目录的 `打开维语配音.command` 也可打开系统浏览器。默认端口 8767，不安装登录启动项。
3. 直接生成：将用户文稿保存为私人目录中的 UTF-8 文件，执行：

```sh
"<data>/.venv/bin/python" "<skill>/scripts/synthesize.py" --text-file "<稿件.txt>" --voice "<音色ID>"
```

省略 `--voice` 使用默认音色；省略 `--output` 会在 `<data>/outputs` 生成独立 WAV 和 JSON。最多 2000 字符，建议每段 1–3 句话。单次选择不修改默认音色；用户要修改默认时使用 `voices.py set-default <id>`。

生成默认离线。报告实际阶段与输出 JSON 的耗时，不虚构百分比。完成后检查 WAV 可解码、非静音，提供绝对路径的音频预览。维语自然度与音色相似度需用户试听，机器转写不等于人工质量验证。

## 添加或改善音色

确认用户本人或对方已授权；沿用已有会话或保存的授权，无需反复询问。选 3–10 秒清晰的单人维语及逐字文稿。视频提取、剪切或转 MP3 使用可用的 FFmpeg 技能。

用户不方便转写时，已有本地 ASR 可运行：

```sh
"<data>/.venv/bin/python" "<skill>/scripts/transcribe.py" --audio "<参考.wav>" --output "<机器稿.txt>"
```

机器稿应标为未人工核对。用户允许按机器稿试听时使用 `automatic_draft_user_approved_for_trial`，不要强迫人工转写，也不能自行改成 `human_verified`。具体添加命令、路径、故障处理见 [工作流](references/workflow.md)。不要加载来源不明的 `.pt` 提示文件。

## 模型范围

复用已有的 OmniVoice 0.2.1 与 PyTorch 环境。原版“扎提skill”是另一个中文配音工作流，使用 `$macos-local-voice`；保留其环境和数据。

OmniVoice 源码为 Apache-2.0，预训练权重为 CC-BY-NC。用户提出商业用途时说明权重限制，核实许可或选择适合的模型。来源：[官方仓库](https://github.com/k2-fsa/OmniVoice)、[权重许可](https://huggingface.co/k2-fsa/OmniVoice#license)。
