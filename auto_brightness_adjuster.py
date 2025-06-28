import time
import datetime
import numpy as np
import json
import os
from PIL import ImageGrab
import wmi
import keyboard
import threading
import tkinter as tk
from tkinter import messagebox
import pythoncom
import math

CONFIG_FILE = "brightness_config.json"

# Default settings
default_config = {
    "max_brightness": 100,
    "min_brightness": 30,
    "night_limit": 60,
    "screen_poll_interval": 0.5,
    "hotkey": "ctrl+shift+b"
}

# Load or create config
def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Brightness control for built-in screen
def set_brightness(level):
    try:
        wmi_interface = wmi.WMI(namespace='wmi')
        methods = wmi_interface.WmiMonitorBrightnessMethods()[0]
        methods.WmiSetBrightness(int(level), 0)
        print(f"[OK] Brightness set to {level:.0f}%")
    except Exception as e:
        print(f"[ERROR] Failed to set brightness: {e}")

# Get average screen brightness
def get_average_screen_brightness():
    img = ImageGrab.grab().convert('L')  # Grayscale
    avg_brightness = np.array(img).mean()
    print(f"[INFO] Screen brightness: {avg_brightness:.2f}")
    return avg_brightness

# Brightness logic based on screen content
def brightness_from_screen(avg_brightness, config):
    raw = 300 - avg_brightness * 1.5
    clamped = np.clip(raw, config["min_brightness"], config["max_brightness"])
    return int(round(clamped / 10) * 10)  # round to nearest 10

# Night-time limit (can be overridden via config)
def time_of_day_limit(level, config):
    hour = datetime.datetime.now().hour
    if 22 <= hour or hour < 6:
        return min(level, config["night_limit"])
    return level

class BrightnessApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Brightness Quick Settings")
        self.root.geometry("300x300")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.config = load_config()
        self.entries = {}

        # Create UI
        row = 0
        for key in default_config:
            val = self.config.get(key, default_config[key])
            tk.Label(root, text=key).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            entry = tk.Entry(root)
            entry.insert(0, str(val))
            entry.grid(row=row, column=1, padx=10, pady=5)
            self.entries[key] = entry
            row += 1


        save_btn = tk.Button(root, text="Save Settings", command=self.save_settings)
        save_btn.grid(row=row, column=0, columnspan=2, pady=10)

        self.root.withdraw()  # start hidden

        # Start brightness loop in a separate thread
        self.running = True
        threading.Thread(target=self.brightness_loop, daemon=True).start()

        # Listen for hotkey to toggle window
        threading.Thread(target=self.hotkey_listener, daemon=True).start()

    def save_settings(self):
        for key, entry in self.entries.items():
            val = entry.get().strip()
            if key == "hotkey":
                self.config[key] = val  # save as plain string
            else:
                try:
                    self.config[key] = float(val) if '.' in val else int(val)
                except ValueError:
                    messagebox.showwarning("Invalid input", f"Invalid input for {key}, keeping previous value.")
                    entry.delete(0, tk.END)
                    entry.insert(0, str(self.config[key]))
        save_config(self.config)
        messagebox.showinfo("Settings", "Settings saved successfully!")


    def brightness_loop(self):
        pythoncom.CoInitialize()
        while self.running:
            try:
                avg = get_average_screen_brightness()
                target = brightness_from_screen(avg, self.config)
                capped = time_of_day_limit(target, self.config)
                set_brightness(capped)
                time.sleep(self.config.get("screen_poll_interval", 0.5))
            except Exception as e:
                print(f"[FATAL] {e}")
                time.sleep(5)

    def hotkey_listener(self):
        current_hotkey = self.config.get("hotkey", "ctrl+shift+b").lower()
        print(f"[INFO] Listening for hotkey: {current_hotkey}")
        while self.running:
            try:
                if keyboard.is_pressed(current_hotkey):
                    self.root.after(0, self.toggle_window)
                    time.sleep(1)  # debounce
            except:
                pass
            time.sleep(0.1)

    def toggle_window(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
            self.root.lift()
        else:
            self.root.withdraw()

    def hide_window(self):
        self.root.withdraw()

    def stop(self):
        self.running = False

def main():
    root = tk.Tk()
    app = BrightnessApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.stop()
        print("\n[EXIT] Exiting on user request.")

if __name__ == "__main__":
    main()
