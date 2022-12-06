#!/bin/env python3
import sys
import os
import re
import hashlib
import json
import shutil
import getch
from render import main as render
from pyzbar.pyzbar import decode
from pyparsing import *

ANSI_RESET = "\u001b[0m"
ANSI_CURSOR_UP = "\u001b[A"


config = open(os.path.join(os.getenv("HOME"), ".newsboat/config")).read()
browser = re.search("browser ([^\n]*?)\n", config)
browser = browser.group(1) if browser else os.getenv("BROWSER", "")
columns = shutil.get_terminal_size().columns
rows = shutil.get_terminal_size().lines
bar_rows = 0
page_rows = rows
previous_row_count = 0
content = ""
lines = []
lines_length = 0

stdout = sys.stdout
index = 0
help = "q:Quit space:Next r:Refresh g:Top G:Bottom Number:Select link"
bar_content = help
raw = None

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


def get_uncolor(string):
    ESC = Literal("\x1b")
    integer = Word(nums)
    escapeSeq = Combine(
        ESC + "[" + Optional(delimitedList(integer, ";")) + oneOf(list(alphas))
    )
    nonAnsiString = lambda s: Suppress(escapeSeq).transformString(s)
    return nonAnsiString(string)


def get_length(string):
    return len(get_uncolor(string))


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
    return lines


def get_content():
    global content
    global lines
    global raw
    global lines_length
    global index
    global columns
    percent = None
    if lines and raw:
        percent = index / lines_length
        content = render(raw)
    elif len(sys.argv) == 2:
        file_path = sys.argv[-1]
        raw = None
        content = open(file_path).read()
    else:
        d = json.load(open("/tmp/newsboat_current.json"))
        file_path = d["file"]
        raw = d["raw"]
        content = open(file_path).read()
    lines = content.split("\n")
    # lines = wrap_width(lines, columns)
    lines_length = len(lines)
    if percent != None:
        index = int(percent * lines_length)


def update_bar_content(content, ender="", update=False):
    global bar_content
    if update:
        ender = "{}/{} {}%".format(
            index + page_rows,
            lines_length,
            round(min(100, 100 * (index + page_rows) / lines_length), 1),
        )
    bar_content = content + " " * (columns - len(content + ender)) + ender


def print_screen(content, bottom=True):
    global previous_row_count

    stdout.write(ANSI_CURSOR_UP * previous_row_count)
    stdout.write(
        content
        + (
            get_colorful_str("\n" + bar_content, "white__lighter_blue", str, "\r")
            if bottom
            else "\r"
        )
    )
    # stdout.write("\n")
    stdout.flush()
    previous_row_count = rows


def down(step=page_rows):
    global index
    index += step
    scroll(True, step)


last_index = 0


def scroll(init_bar=False, step=None):
    global index
    global last_index
    global page_rows
    global bar_rows
    page_rows = rows - 1
    raw_index = index
    index = max(0, index)
    index = min(lines_length - page_rows, index)
    if last_index != index or step in [0, "bar"]:
        if init_bar:
            update_bar_content(help, update=True)
        bar_rows = (len(bar_content) + columns - 1) // columns
        result = lines[index : index + page_rows]
        result = result + [get_colorful_str(" " * columns)] * (page_rows - len(result))
        print_screen("\n".join(result))
        last_index = index


def up(step=page_rows):
    global index
    index -= step
    scroll(True, step)


def change_bar(content, prefix=""):
    if content:
        update_bar_content(prefix + content)
    else:
        update_bar_content(help, update=True)
    scroll(step=0)


current_link = ""


def link_bar(string):
    global current_link
    d = links.get(string, {})
    if d:
        current_link = d.get("link")
        change_bar(d.get("string"))
    elif string:
        change_bar(string, "link: ")
    else:
        change_bar(string, "link: ")


def result_bar(string):
    change_bar(os.popen(string[8:]).read(), "")


links = {}


def get_links():
    global links
    for link_id, link, link_type in re.findall(
        "\[(\d+)\]: ([^ ]*?) \((.*?)\)", content, re.S
    ):
        l = "[{}]: {} ({})".format(link_id, link, link_type)
        if "image" == link_type:
            img_path = (
                "/tmp/newsboat_"
                + hashlib.md5(link.encode("utf8")).hexdigest()
                + "."
                + (link.split(".")[-1] or "jpg")
            )
            links[link_id] = dict(string="{} local:{}".format(l, img_path), link=link)
        else:
            links[link_id] = dict(string=l, link=link)


def watch():
    global columns
    global rows
    global current_link
    tmp_key = ""
    mode = ""
    get_content()
    down(0)
    get_links()
    while True:
        cols = shutil.get_terminal_size().columns
        rows = shutil.get_terminal_size().lines
        if cols != columns:
            columns = cols
            get_content()
            down(0)

        key = getch.getch()
        if tmp_key == "\x1b[":
            if key == "A":
                up(10)
            elif key == "B":
                down(10)
            tmp_key = ""
        elif mode == "command":
            if key == "\n":
                result_bar(tmp_key)
                tmp_key = mode = ""
            elif key == "\x7f":
                tmp_key = tmp_key[:-1]
                change_bar(tmp_key)
                if not tmp_key:
                    mode = ""
            else:
                tmp_key += key
                change_bar(tmp_key)
        elif mode == "link":
            if key == "\n":
                tmp_key = mode = ""
                if current_link:
                    os.system(browser + " " + current_link)
            elif key == "\x7f":
                tmp_key = tmp_key[:-1]
                link_bar(tmp_key)
                if not tmp_key:
                    mode = ""
            elif key.isdigit():
                tmp_key += key
                link_bar(tmp_key)
            else:
                tmp_key = mode = ""
        elif key == " ":
            down()
        elif key == "r":
            columns = cols
            get_content()
            down(0)
        elif key == "q":
            print_screen("\n".join([" " * columns] * rows), bottom=False)
            break
        elif key == "\x03":
            print_screen("\n".join([" " * columns] * rows), bottom=False)
            exit()
        elif key == "\x1b":
            tmp_key = "\x1b"
        elif key == "[" and tmp_key == "\x1b":
            tmp_key += "["
        elif key.isdigit():
            mode = "link"
            tmp_key = key
            link_bar(tmp_key)
        elif key == "\n":
            change_bar("")
            print_screen("\n".join([" " * columns] * page_rows))
            down(0)
        elif key == ":":
            mode = "command"
            change_bar(mode)
        elif key == "G":
            down(lines_length)
        elif key == "g":
            up(lines_length)
        else:
            pass
            # print([key])


if __name__ == "__main__":
    watch()
