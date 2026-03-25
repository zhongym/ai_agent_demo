---
name: image_ocr_extract
description: 执行固定的 OCR Python 脚本提取图片文字，再按用户目标回答，例如提取原文、总结内容、判断图片用途或分析文档类型。
---

# 目标
当用户希望理解图片 URL 里的文字内容时，先调用 `run_shell_command` 执行固定 OCR 脚本，再根据用户问题完成提取、总结、归类或用途分析。

# 适用问题
- 请帮我识别这张图片里的文字：https://example.com/a.png
- 提取这两张截图里的内容：https://example.com/1.png https://example.com/2.png
- 帮我做 OCR，把图片 URL 里的文字提取出来
- 这张图片大概是干嘛的：https://example.com/doc.png
- 帮我判断这张图像是订单、报表还是别的单据：https://example.com/form.png
- 总结一下这张截图主要表达了什么：https://example.com/page.png

# 执行要求
1. 当用户问题里包含图片 URL，且用户目标属于以下任一类型时，都可以使用这个 skill：
   - 提取文字 / OCR
   - 总结图片中的文字内容
   - 判断图片大概是干嘛的
   - 判断图片对应的文档类型、业务用途或场景
   - 提炼关键信息
2. 从问题文本中提取全部图片 URL。
3. 如果没有提取到 URL，先向用户澄清，不要调用工具。
4. 只处理 `http` 或 `https` 的公开图片 URL；如果用户给的是别的协议，直接说明不支持。
5. 调用 `run_shell_command` 时，固定传入：
   - `working_directory="."`
   - 命令：
     - `.venv/bin/python app/skills/ocr/ocr_runner.py "<url1>" "<url2>" ...`
6. `app/skills/ocr/ocr_runner.py` 是仓库内固定脚本，不要再动态创建 Python OCR 脚本，也不要把 OCR 逻辑写进单行 `python -c`。
7. `ocr_runner.py` 会自己负责：
   - 校验 URL 只能是 `http/https`
   - 下载图片到 `/tmp`
   - 如果缺少 `rapidocr_onnxruntime` 或 `pillow`，只在缺依赖时自动安装一次
   - 调用 OCR
   - 输出 JSON 到 stdout，结构至少包含：
     - `items`
     - 每个 item 至少包含：
       - `image_index`
       - `url`
       - `file_name`
       - `raw_text`
8. 如果 `run_shell_command` 返回 `success=false`，不要继续总结 OCR 内容，直接根据 stderr 向用户解释失败原因。
9. 不要生成最终文件，不要假设系统里已有 OCR 依赖。
10. 把 OCR 结果看作“理解图片文字内容的中间步骤”，不要机械地只回传原文。
11. 在组织最终回答前，先判断用户真正想要的是什么：
   - 如果用户要“提取文字 / OCR原文”，重点返回原文
   - 如果用户要“总结内容”，重点给摘要，原文放后面或按需省略
   - 如果用户要“图片是干嘛的 / 这是什么单据 / 这页在说什么”，先基于 OCR 文本判断用途、文档类型、场景和关键字段，再给结论
   - 如果 OCR 文本不足以支持判断，要明确说明判断依据有限，不要过度脑补

# 输出要求
- 回答格式跟随用户目标，不要固定成一个模板
- 默认优先回答用户真正的问题，再决定是否附上 OCR 原文
- 只有在这些场景下，强烈建议附上 `OCR原文`：
  - 用户明确要原文
  - 用户要校对识别结果
  - 你对用途判断不够确定，需要展示依据
- 如果用户问“这张图片是干嘛的”，优先输出：
  - 一句话结论
  - 判断依据（来自哪些文字）
  - 可选：关键字段
- 如果用户问“这是什么单据/页面/内容”，优先输出：
  - 类型判断
  - 主要用途
  - 关键字段或关键信息
- 如果用户没有明确指定格式，回答保持简洁，并提示 OCR 结果可能存在识别误差
