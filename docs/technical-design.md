# Streamify — B站/YouTube 视频下载 CLI 工具技术方案

## Context

构建一个 CLI 工具，输入 B站或 YouTube 视频链接，下载视频到本地。**主要通过 Claude Code 调用**，也可直接在终端使用。项目从零开始。

### 已确认的决策

- **语言**：Python
- **下载后端**：yt-dlp 统一处理（B站 + YouTube）
- **CLI 框架**：Typer
- **分发**：pipx install
- **默认下载目录**：
  - B站视频 → `~/Documents/B站视频/`
  - YouTube视频 → `~/Documents/YouTube视频/`
- **使用方式**：主要通过 Claude Code 调用（用户给链接 + 清晰度要求），也支持直接终端使用

---

## 项目结构

```
Streamify/
  pyproject.toml              # 项目元数据、依赖、入口点
  src/
    streamify/
      __init__.py
      cli.py                  # Typer CLI，参数解析，命令定义
      core/
        __init__.py
        downloader.py          # 下载器抽象接口（Protocol）
        ytdlp_backend.py       # yt-dlp 实现
        url_router.py          # URL → 平台识别 + 默认目录路由
      config.py                # 默认配置 + 配置文件加载
      progress.py              # Rich 进度条，对接 yt-dlp 回调
  tests/
    test_url_router.py
    test_downloader.py
    test_cli.py
```

## 核心依赖

- **yt-dlp** — 下载引擎（Python 库直接调用）
- **typer[all]** — CLI 框架（含 Rich）
- **rich** — 进度条、美化输出
- **ffmpeg**（外部依赖）— 音视频合并

## CLI 接口设计

```bash
# 基本用法 — 自动识别平台，下载到对应默认目录
streamify "https://www.bilibili.com/video/BV1xx411c7mD"
# → 下载到 ~/Documents/B站视频/

streamify "https://youtu.be/dQw4w9WgXcQ"
# → 下载到 ~/Documents/YouTube视频/

# 指定目录
streamify <URL> -o ~/Desktop

# 指定清晰度
streamify <URL> -q 1080
streamify <URL> -q 720
streamify <URL> -q best          # 默认值

# 其他选项
streamify <URL> --audio-only                     # 仅提取音频
streamify <URL> --cookies-from-browser chrome     # B站1080p+需要
streamify <URL> --list-formats                    # 列出可用格式
streamify <URL> --subtitle                        # 下载字幕
streamify <URL> --proxy socks5://...              # 代理
```

## 核心流程

```
Claude Code / 用户输入 URL + 选项
    ↓
url_router 识别平台（bilibili / youtube / unknown）
    ↓
确定输出目录：
  - 用户指定 -o → 用指定目录
  - 未指定 → bilibili: ~/Documents/B站视频/
             youtube:  ~/Documents/YouTube视频/
    ↓
生成平台特定 yt-dlp 配置
  - B站: 默认下载字幕、设置 User-Agent、referer
  - YouTube: 标准 yt-dlp 配置
    ↓
合并清晰度选项（-q 映射为 yt-dlp format selector）
    ↓
yt_dlp.YoutubeDL(opts).download([url])
    ↓
Rich 进度条显示下载状态
    ↓
下载完成 → 输出文件路径和信息
```

## 关键设计点

### 1. URL 路由器（`url_router.py`）
- 正则匹配 URL，识别平台：`bilibili.com`/`b23.tv` → bilibili，`youtube.com`/`youtu.be` → youtube
- 返回平台名称 + 默认输出目录 + 平台特定 yt-dlp 选项

### 2. 下载器接口（`downloader.py`）
- 定义 `Downloader` Protocol：`download(url, options)` / `list_formats(url)` / `extract_info(url)`
- 预留接口，未来可插入 bilix/BBDown 后端

### 3. yt-dlp 后端（`ytdlp_backend.py`）
- 直接 `import yt_dlp` 作为 Python 库使用
- 清晰度映射：`-q 1080` → `format: "bestvideo[height<=1080]+bestaudio/best[height<=1080]"`
- B站 cookie：支持 `--cookies-from-browser`，如果检测到最高只有 720p 自动提示
- 进度回调：注册 `progress_hooks` 驱动 Rich 进度条

### 4. 进度显示（`progress.py`）
- Rich Progress bar，显示：文件名、百分比、速度、ETA
- 下载完成后打印摘要：文件路径、大小、格式

### 5. 错误处理
- 网络/地区限制 → 提示 `--proxy`
- B站需登录 → 提示 `--cookies-from-browser chrome`
- ffmpeg 缺失 → 启动时检查 `shutil.which("ffmpeg")`，警告
- 无效 URL → 友好错误信息

## 实现顺序

1. **脚手架**：pyproject.toml、包结构、入口点
2. **URL 路由器**：平台识别 + 默认目录
3. **yt-dlp 后端**：下载核心逻辑
4. **CLI 命令**：Typer app 串联所有组件
5. **进度条**：Rich 进度显示
6. **错误处理**：友好提示
7. **测试**：单元测试 + CLI 测试
8. **安装**：pipx install . 可用

## 需修改/创建的文件

- `/Users/leo/aiproject/content-os/Streamify/pyproject.toml`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/__init__.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/cli.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/core/__init__.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/core/downloader.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/core/ytdlp_backend.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/core/url_router.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/config.py`（新建）
- `/Users/leo/aiproject/content-os/Streamify/src/streamify/progress.py`（新建）

## 验证方式

1. `pipx install .` 成功安装
2. `streamify "https://www.bilibili.com/video/BV1xx411c7mD"` → 下载到 ~/Documents/B站视频/
3. `streamify "https://youtu.be/<video_id>"` → 下载到 ~/Documents/YouTube视频/
4. `streamify <URL> -o ~/Desktop -q 720` → 指定目录和清晰度
5. `streamify <URL> --list-formats` → 列出格式
6. `pytest` 跑通测试
