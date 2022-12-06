#!/bin/env python3
import sys
import markdownify
import os
import requests
import re
import hashlib
import json
import time
import shutil
import _thread
import bs4
from pyparsing import *
from PIL import Image
from pyzbar.pyzbar import decode, ZBarSymbol

timeout = 2
padding = 3
wipe_ass = True

margin_column_count = None
margin_row_count = None


stdout = sys.stdout
ANSI_RESET = "\u001b[0m"
ANSI_CURSOR_UP = "\u001b[A"
COLORS = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
}
STYLES = [
    "reset",
    "lighter",
    "darker",
    "italic",
    "underline",
    "slow_blinking",
    "fast_blinking",
    "reverse",
    "hide",
    "cross-out",
]


IMAGE_HEADERS = {
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Connection": "keep-alive",
    "DNT": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

urls = []
max_url_length = 0
images_amount = 0
raw_path = sys.argv[-1]
file_path = raw_path
stop = False
previous_row_count = 0
host = ""


def get_colorful_str(s, color="", fun=str, ender=""):
    c = color.split("__")
    lc = len(c)
    f = b = ""
    if lc == 1:
        f = color
    elif lc == 2:
        f, b = c
    if "_" in f:
        fs, f = f.split("_")
        fs = STYLES.index(fs)
    else:
        fs = 0
    if "_" in b:
        bs, b = b.split("_")
        bs = STYLES.index(bs)
    else:
        bs = 0
    if f:
        f = "\033[{};{}m".format(fs, COLORS[f])
    if b:
        b = "\033[{};{}m".format(bs, COLORS[b] + 10)
    if f + b:
        return "{}{}{}\033[0m".format(f, b, fun(s)) + ender
    else:
        return str(fun(s)) + ender


def get_length(string):
    ESC = Literal("\x1b")
    integer = Word(nums)
    escapeSeq = Combine(
        ESC + "[" + Optional(delimitedList(integer, ";")) + oneOf(list(alphas))
    )

    nonAnsiString = lambda s: Suppress(escapeSeq).transformString(s)

    unColorString = nonAnsiString(string)
    return len(unColorString)


def get_sorted_filenames(dirname, ext):
    return (
        de.name
        for de in sorted(os.scandir(dirname), key=lambda de: de.name)
        if de.is_file() and de.name.endswith("." + ext)
    )


def get_txt_frames(display_dirname):
    return [
        open("{}/{}".format(display_dirname, filename)).read()
        for filename in get_sorted_filenames(display_dirname, "txt")
    ]


def display_txt_frames(txt_frames, seconds_per_frame):
    global margin_column_count
    global margin_row_count
    global previous_row_count
    global padding

    columns = shutil.get_terminal_size().columns
    rows = shutil.get_terminal_size().lines
    frame_row_count = len(txt_frames[0].split("\n"))
    frame_column_count = get_length(txt_frames[0].split("\n")[0])
    disable = False
    if frame_row_count > rows or frame_column_count > columns:
        frame_row_count = rows
        frame_column_count = columns
        disable = True

    while padding > 0 and padding * 2 + frame_row_count > rows:
        padding -= 1
    if margin_column_count and margin_column_count < 0:
        margin_column_count = None
    if margin_row_count and margin_row_count < 0:
        margin_row_count = None

    if margin_column_count is None:
        margin_column_count = (columns - frame_column_count) // 2
    if margin_row_count is None:
        margin_row_count = (rows - frame_row_count - padding * 2) // 2
    display_row_count = padding * 2 + frame_row_count
    total_row_count = margin_row_count + display_row_count
    total_column_count = margin_column_count * 2 + frame_column_count

    try:
        while not stop:
            for i in range(len(txt_frames)):
                if stop:
                    return
                txt_frame = txt_frames[i]
                progress_ratio = (
                    round(100 * len(urls) / images_amount, 1) if images_amount else 100
                )
                progress = " {}% ".format(progress_ratio)
                progress += (
                    int(
                        (100 - progress_ratio) / 100 * frame_column_count
                        - len(progress)
                    )
                    * "━"
                )
                progress = progress.rstrip()

                progress = (
                    get_colorful_str(
                        (frame_column_count - len(progress)) * "━", "lighter_cyan"
                    )
                    + progress
                )
                lines = (urls[::-1] + [""] * display_row_count)[:display_row_count]
                lines = list(
                    map(
                        lambda x: x.strip().center(total_column_count, " ")[
                            :total_column_count
                        ]
                        if len(x) <= total_column_count or x.endswith("   ")
                        else x[: total_column_count - 3] + "...",
                        lines,
                    )
                )
                if disable:
                    txt_frame = lines[:-1] + [progress + "\r"]
                else:
                    txt_frame = txt_frame.split("\n")[:-1] + [progress]

                txt_frame = [
                    lines[padding + i][:margin_column_count]
                    + v
                    + lines[padding + i][margin_column_count + frame_column_count :]
                    for i, v in enumerate(txt_frame)
                ]
                lines = (
                    lines[:padding]
                    + txt_frame
                    + (lines[-padding:] if padding > 0 else [])
                )
                lines = margin_row_count * [""] + lines
                # lines = list(map(str.rstrip, lines))
                txt_frame = "\n".join(lines)
                stdout.write(ANSI_CURSOR_UP * previous_row_count)
                stdout.write(txt_frame)
                # stdout.write("\n")
                stdout.flush()
                previous_row_count = total_row_count
                time.sleep(seconds_per_frame)
        stdout.write(ANSI_RESET)
    except KeyboardInterrupt:
        stdout.write(ANSI_RESET)
        stdout.write("\n")
        stop_display()
    stdout.flush()


def display():
    display_dirname = os.path.join(BASE_DIR, "gif")
    seconds_per_frame = 0.06
    txt_frames = get_txt_frames(display_dirname)
    display_txt_frames(txt_frames, seconds_per_frame)


def stop_display():
    global stop
    stop = True
    if wipe_ass:
        stdout.write(ANSI_CURSOR_UP * (previous_row_count + 1))
        stdout.write(ANSI_RESET)
        stdout.flush()


def improve_html(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    for ele in soup.find_all("div"):
        if "display:none" in ele.get("style", "").replace(" ", ""):
            html = html.replace(str(ele), "")

    for ele in soup.find_all("script"):
        html = html.replace(str(ele), "")

    html = re.sub("<(/)?t[dr][^>]*?>", r"<\1div>", html)
    html = re.sub('<img [^>]*?file=("[^>]*?")[^>]*?>', r"<img src=\1 />", html)
    return html


def get_url(url, host):
    if url.startswith("http"):
        pass
    elif url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = host + url
    else:
        url = host + "/" + url
    return url


def generate():
    global urls
    global images_amount
    global max_url_length
    global file_path
    global host
    columns = shutil.get_terminal_size().columns
    column_ender = "." + str(columns // 10)
    html = improve_html(open(raw_path).read())
    host = re.search("Link: (https://[^/ ]*)", html).group(1)
    html = markdownify.markdownify(
        html, heading_style="ATX", wrap=True, wrap_width=columns
    )
    open(raw_path, "w").write(html)
    html_url = re.search("Link: (https?://.*?)\n", html).group(1)
    read_file_path = (
        "/tmp/newsboat_"
        + hashlib.md5(html_url.encode("utf8")).hexdigest()
        + column_ender
    )
    if os.path.isfile(read_file_path):
        file_path = read_file_path
        html = open(file_path).read()
    else:
        _thread.start_new_thread(display, ())
        imgs = {}
        for i in re.findall("!\[.*?\]\(.*?\)", html):
            imgs[i] = re.search("\((.*?)\)", i).group(1)
        images_amount = len(imgs)
        for img_element, url in imgs.items():
            url = get_url(url, host)
            url_len = len(url)
            max_url_length = max(url_len, max_url_length)
            end_string = " " * (max_url_length - url_len)
            urls.append("GET " + url + end_string)
            ender = url.split(".")[-1]
            if len(ender) > 4:
                ender = "jpg"
            img_path = (
                "/tmp/img_newsboat_"
                + hashlib.md5(url.encode("utf8")).hexdigest()
                + "."
                + ender
            )
            if not os.path.isfile(img_path):
                try:
                    open(img_path, "wb").write(
                        requests.get(
                            url, timeout=timeout, headers=IMAGE_HEADERS
                        ).content
                    )
                except requests.exceptions.RequestException:
                    urls[-1] = "ERR " + url + end_string
                    continue
            try:
                for q in decode(Image.open(img_path), symbols=[ZBarSymbol.QRCODE]):
                    q = q.data.decode("utf8")
                    html = html.replace(
                        img_element,
                        "{} [_qrcode_]({})".format(img_element, q),
                    )
            except:
                pass

            urls[-1] = "GOT " + url + end_string
            content = os.popen("tiv 2>/dev/null " + img_path).read()
            html = html.replace(
                img_element,
                "\n```\n{}\n```\n{}".format(
                    content,
                    img_element,
                ),
            )
        html = parse_markdown(html)
        html = wrap_width(html.split("\n"), columns)
        open(read_file_path, "w").write(html)
        file_path = read_file_path
        stop_display()
    return html


def parse_markdown(content):
    content = re.sub("Link: (https?://.+)\n", r"Link: [\1](\1)\n", content, count=1)
    columns = shutil.get_terminal_size().columns
    result = []
    page_urls = []
    img = re.compile("!\[([^\[\]]*?)\]\(([^\(\)]*?)\)")
    link = re.compile("\[([^\[\]]*?)\]\(([^\(\)]*?)\)")
    qr_link = re.compile("\[_qrcode_\]\(([^\(\)]*?)\)")
    bold = re.compile("\*\*(.*?)\*\*")
    italic = re.compile("\*(.*?)\*")
    for l in content.split("\n"):
        l = l.rstrip()
        if l.startswith("# "):
            l = get_colorful_str(l[1:], "white__lighter_cyan")
        elif l.startswith("## "):
            l = get_colorful_str(l, "lighter_cyan")
        elif l.startswith("### "):
            l = get_colorful_str(l, "cyan")
        elif l.startswith("#### "):
            l = get_colorful_str(l, "lighter_blue")
        elif l.startswith("##### "):
            l = get_colorful_str(l, "blue")
        elif re.search("#+ ", l):
            l = get_colorful_str(l, "blue")
        elif bold.search(l):
            bold_search = bold.search(l)
            name = bold_search.group(1)
            l = l.replace(bold_search.group(0), get_colorful_str(name, "lighter_cyan"))
        elif italic.search(l):
            italic_search = italic.search(l)
            name = italic_search.group(1)
            l = l.replace(
                italic_search.group(0), get_colorful_str(name, "italic_white")
            )
        while img.search(l):
            img_search = img.search(l)
            name, url = img_search.groups()
            name = name.strip()
            string = "{} (image)".format(url)
            if string in page_urls:
                index = page_urls.index(string)
            else:
                index = len(page_urls)
                page_urls.append(string)

            if name:
                name += ":"
            l = l.replace(
                img_search.group(0),
                get_colorful_str("[image {}{}]".format(name, index), "underline_cyan"),
            )
        while qr_link.search(l):
            link_search = qr_link.search(l)
            url = link_search.group(1)
            string = "{} (qrcode)".format(url)
            if string in page_urls:
                index = page_urls.index(string)
            else:
                index = len(page_urls)
                page_urls.append(string)
            l = l.replace(
                link_search.group(0),
                get_colorful_str("[qrcode {}]".format(index), "underline_cyan"),
            )
        while link.search(l):
            link_search = link.search(l)
            name, url = link_search.groups()
            name = name.strip()
            string = "{} (link)".format(url)
            if string in page_urls:
                index = page_urls.index(string)
            else:
                index = len(page_urls)
                page_urls.append(string)
            l = l.replace(
                link_search.group(0),
                get_colorful_str("{}[{}]".format(name, index), "underline_cyan"),
            )
        result.append(l)
    result.append("")
    for i, v in enumerate(page_urls):
        v = get_url(v, host)
        v = "[{}]: {}".format(i, v)
        result.append(get_colorful_str(v, "cyan"))

    return "\n".join(result)


def wrap_width(tmp_lines, c):
    max_ord = 11903
    lines = []
    skip = False
    length = 0
    for l in tmp_lines:
        if l == "```":
            skip = not skip
            length = 0
            continue
        if skip:
            length = length or get_length(l)
            l = [l + " " * (c - length)]
        else:
            length = get_length(l)
            if len(l.encode("utf8")) != len(l):
                ls = []
                while l:
                    tmp_c = 0
                    b = True
                    for i, v in enumerate(l):
                        tmp_c += 2 if ord(v) > max_ord else 1
                        if tmp_c >= c:
                            tmp_c = 0
                            tmp_l = l[:i]
                            ll = sum(
                                1 if ord(i) > max_ord else 0 for i in l
                            ) + get_length(tmp_l)
                            ls.append(l[:i] + " " * (c - ll))
                            l = l[i:]
                            b = False
                            break
                    if b:
                        ll = sum(1 if ord(i) > max_ord else 0 for i in l) + get_length(
                            l
                        )
                        ls.append(
                            l + " " * (c - ll),
                        )
                        l = ""
                        break
                l = ls
            elif length > c:
                l = [
                    l[:c],
                    l[c:] + " " * (2 * c - length),
                ]
            else:
                l = [l + " " * (c - length)]
        lines += l
    return "\n".join(lines)


def main(path=""):
    global raw_path
    if path:
        raw_path = path
    try:
        os.system("clear -x")
        return generate()
    except KeyboardInterrupt:
        stop_display()
        os.system("less " + raw_path)


if __name__ == "__main__":
    main()
    open("/tmp/newsboat_current.json", "w").write(
        json.dumps(dict(file=file_path, raw=raw_path))
    )
