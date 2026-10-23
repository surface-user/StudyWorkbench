"""Generate an original six-second VP9 fixture with a development-only FFmpeg."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / ".local/test-tools"))
try:
    import imageio_ffmpeg
except ImportError:
    raise SystemExit("Install dev tool: python -m pip install --target .local/test-tools imageio-ffmpeg==0.6.0") from None

output = root / ".local/sample.webm"
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24",
                "-t", "6", "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", str(output)], check=True)
print(output)
