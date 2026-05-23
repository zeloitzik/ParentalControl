import tkinter as tk
from tkinter import simpledialog
import sys
import os
import argparse
from pathlib import Path

PARENT_PIN_PATH = Path(os.getenv('APPDATA', '')) / "Warden" / "parent_pin.txt"
DEFAULT_PIN = "1234"


def load_parent_pin():
    """Load the parent PIN from the local config file (Option A)."""
    try:
        if PARENT_PIN_PATH.exists():
            return PARENT_PIN_PATH.read_text().strip()
    except Exception:
        pass
    return DEFAULT_PIN


class Screen:
    def __init__(self, target_app=None):
        self.root = None
        self.target_app = target_app

    def create_lock_screen(self):
        self.root = tk.Tk()

        # Make it full screen
        self.root.attributes("-fullscreen", True)
        # Keep it on top of all other windows
        self.root.attributes("-topmost", True)
        # Remove the 'X' and minimize buttons
        self.root.overrideredirect(True)
        # Dark base background
        self.root.configure(bg='#0a0f1a')

        # Main container — centered card with blue accent border
        main_frame = tk.Frame(
            self.root, bg='#111827',
            highlightbackground="#005A9C", highlightthickness=3
        )
        main_frame.place(relx=0.5, rely=0.5, anchor='center', width=820, height=460)

        # Shield icon
        icon_label = tk.Label(
            main_frame, text="🛡️",
            font=("Segoe UI Emoji", 56),
            fg="#3b82f6", bg="#111827"
        )
        icon_label.pack(pady=(35, 5))

        # Title
        title_label = tk.Label(
            main_frame, text="TIME RESTRICTED",
            font=("Segoe UI", 34, "bold"),
            fg="#e0e7ff", bg="#111827"
        )
        title_label.pack(pady=5)

        # Subtitle
        sub_label = tk.Label(
            main_frame,
            text="Your screen time for this application has ended.\nPlease contact your parent to unlock.",
            font=("Segoe UI", 15),
            fg="#93c5fd", bg="#111827",
            justify="center"
        )
        sub_label.pack(pady=(5, 20))

        # --- Parent Override Button ---
        override_btn = tk.Button(
            main_frame,
            text="🔑  Parent Override",
            font=("Segoe UI", 13, "bold"),
            fg="#e0e7ff", bg="#1e3a5f",
            activeforeground="#ffffff", activebackground="#005A9C",
            relief="flat", padx=20, pady=8, cursor="hand2",
            command=self._parent_override
        )
        override_btn.pack(pady=(0, 15))

        # --- Close Application Button ---
        if self.target_app:
            close_app_btn = tk.Button(
                main_frame,
                text=f"🛑 Close {self.target_app} & Continue",
                font=("Segoe UI", 13, "bold"),
                fg="#ffffff", bg="#dc2626",
                activeforeground="#ffffff", activebackground="#b91c1c",
                relief="flat", padx=20, pady=8, cursor="hand2",
                command=self._close_target_app
            )
            close_app_btn.pack(pady=(0, 15))

        # Prevent closing with Alt+F4
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Re-assert topmost periodically
        def maintain_topmost():
            if self.root:
                self.root.attributes("-topmost", True)
                self.root.lift()
                self.root.after(100, maintain_topmost)

        maintain_topmost()

        # Subtle usage log display at the bottom
        log_frame = tk.Frame(self.root, bg='#0a0f1a')
        log_frame.pack(side='bottom', fill='x', pady=15)

        self.usage_text = tk.Text(
            log_frame, height=3, width=80,
            font=("Consolas", 10),
            fg="#3b82f6", bg="#0a0f1a",
            borderwidth=0, highlightthickness=0
        )
        self.usage_text.pack(pady=5)
        self.usage_text.config(state='disabled')

        def update_logs():
            if not self.root:
                return
            try:
                log_path = Path(os.getenv('APPDATA', '')) / "Warden" / "usage_display.log"
                if log_path.exists():
                    with open(log_path, "r") as f:
                        lines = f.readlines()
                        last_lines = "".join(lines[-3:])
                        self.usage_text.config(state='normal')
                        self.usage_text.delete('1.0', tk.END)
                        self.usage_text.insert(tk.END, last_lines)
                        self.usage_text.config(state='disabled')
                        self.usage_text.see(tk.END)
            except Exception:
                pass
            self.root.after(2000, update_logs)

        update_logs()

        # Focus force
        self.root.focus_force()

        self.root.mainloop()

    def _parent_override(self):
        """Prompt for parent PIN and close lock screen if correct."""
        # Temporarily allow interaction by lowering topmost
        self.root.attributes("-topmost", False)
        entered_pin = simpledialog.askstring(
            "Parent Override",
            "Enter your Parent PIN to unlock:",
            show='*',
            parent=self.root
        )
        self.root.attributes("-topmost", True)

        if entered_pin is None:
            return  # User cancelled

        correct_pin = load_parent_pin()
        if entered_pin.strip() == correct_pin:
            self.root.destroy()
            self.root = None
        else:
            # Flash red briefly on incorrect PIN
            error_label = tk.Label(
                self.root, text="❌ Incorrect PIN",
                font=("Segoe UI", 14, "bold"),
                fg="#ef4444", bg="#0a0f1a"
            )
            error_label.place(relx=0.5, rely=0.85, anchor='center')
            self.root.after(2000, error_label.destroy)

    def _close_target_app(self):
        """Kill the locked application and close the lock screen."""
        if self.target_app:
            try:
                import psutil
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc.info['name'] and proc.info['name'].lower() == self.target_app.lower():
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception:
                os.system(f"taskkill /F /IM {self.target_app}")
            
            if self.root:
                self.root.destroy()
                self.root = None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", default=None, help="The application executable name that is locked")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    s = Screen(target_app=args.app)
    s.create_lock_screen()
