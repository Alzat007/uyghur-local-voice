# 运行与维护

默认私人目录为 `~/Library/Application Support/uyghur-voice-lab`。TTS 模型放在 `models/OmniVoice`，可选 ASR 在 `models/OmniASR-CTC-300M-v2`，Python 为 `.venv/bin/python`。`voices.json` 保存音色名称、相对提示路径、授权与文稿状态。

已验证 Apple M2 / 16 GB、Python 3.11、omnivoice 0.2.1、torch/torchaudio 2.8.0、transformers 5.21.0、numpy 2.4.6、soundfile 0.14.0。MPS 用 float16，CPU 回退用 float32；音频 tokenizer 自动使用 CPU。ASR 固定 CPU，避免长音频触发 MPS 卷积通道限制。

迁移新机器先检查环境。可用 uv 创建 Python 3.11 venv 并安装上述版本及 scipy。TTS 权重 `k2-fsa/OmniVoice` 约 3.26 GB，可选 ASR `aadel4/omniASR-CTC-300M-v2` 约 1.30 GB。说明下载与磁盘需求，按用户授权安装，已有文件先复用。新机器安装不属于本机已验证范围。

## 添加音色

替换以下绝对路径与用户真实的授权记录：

```sh
"<data>/.venv/bin/python" "<skill>/scripts/voices.py" --data-dir "<data>" add \
  --id "new-voice" --name "新参考音色" \
  --audio "<参考.wav>" --transcript "<逐字稿.txt>" \
  --authorization "<用户真实授权陈述>" --transcript-status human_verified
```

用户同意试用机器稿时，状态改为 `automatic_draft_user_approved_for_trial`，并加 `--trial-authorization "<用户允许试用机器稿的陈述>"`。不得凭空填写。新音色使用独立文件夹；重复 ID 会报错。改参考时创建新 ID，保留旧版便于对比。

## 面板和故障

`python3 <skill>/scripts/launch.py` 幂等启动，`--open` 打开系统浏览器，`--port` 修改端口。仅监听 127.0.0.1，不停止其他服务。前台调试用 `panel.py --port 8767`，Ctrl-C 停止。

一次运行一个任务，CLI 和面板共享推理锁；生成日志为 `logs/<job-id>.log`，文稿和任务记录在 `jobs/`。面板生成超过 20 分钟会终止。页面刷新可追踪任务；服务重启后已完成作品仍在历史中。生成中不要重启服务。

- 缺文件：检查 `voices.py status` 的 missing；按需补齐，别重复下载。
- 发音差：对齐参考音频和逐字文稿；先做短试听，不擅自切换音色。
- 生成失败：查看对应日志；内存不足时缩短稿件，必要时用 CPU。
- 长文：自然分段，每段不超过 2000 字符，保留稿件对应关系。
- 近乎静音或无效数值：脚本报错，不作为成功作品交付。
