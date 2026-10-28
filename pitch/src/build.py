"""Inline fonts, rough.js and the AYUN marks into a single offline HTML file."""
import base64
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
PITCH = HERE.parent
VENDOR = HERE / "vendor"


def data_uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def build(template, out):
    html = (HERE / template).read_text()
    html = html.replace("/*VIRGIL*/", (VENDOR / "virgil.css").read_text())
    html = html.replace("<!--ROUGH-->", (VENDOR / "rough.html").read_text())
    html = html.replace("url(MARK)", "url(" + data_uri(PITCH / "assets/ayun-mark-mask.png", "image/png") + ")")
    html = html.replace("url(WORDMARK)", "url(" + data_uri(PITCH / "assets/ayun-wordmark-mask.png", "image/png") + ")")
    (PITCH / out).write_text(html)
    print(out, len(html) // 1024, "KB")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "demos.template.html", sys.argv[2] if len(sys.argv) > 2 else "demos.html")
