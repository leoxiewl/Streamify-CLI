# Streamify

Download Bilibili and YouTube videos from URL.

## Installation

```bash
pip install -e .
```

## Usage

```bash
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9"
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output PATH` | Output directory | Current directory |
| `-q, --quality TEXT` | Quality: best, 1080, 720, 480 | best |
| `--audio-only` | Audio only (MP3), skips video track | False |
| `--cookies-from-browser BROWSER` | Read cookies from browser (chrome, firefox) | - |
| `--cookies PATH` | Path to Netscape cookie file | - |
| `--subtitle / --no-subtitle` | Download subtitles | Auto (on for Bilibili) |
| `--proxy URL` | Proxy URL (e.g., socks5://127.0.0.1:1080) | - |
| `-F, --list-formats` | List available formats and exit | - |

### Examples

```bash
# Download video (saves as .mp4 + .mp3)
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9"

# Download to specific directory with 1080p quality
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9" -o ~/Videos -q 1080

# Download audio only (MP3)
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9" --audio-only

# List available formats
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9" -F

# Download with proxy
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9" --proxy "socks5://127.0.0.1:1080"

# Download with cookies from Chrome
streamify download "https://www.bilibili.com/video/BV1gX9TBzEk9" --cookies-from-browser chrome
```

### Output Files

By default, video downloads produce two files:
- `.mp4` — Video track
- `.mp3` — Audio track

Use `--audio-only` to download audio only as a single `.mp3` file.

### Bilibili Login

Some Bilibili videos require login to download (e.g., favorited videos, series).

```bash
# Login via QR code
streamify login

# Logout (clear stored session)
streamify logout
```
