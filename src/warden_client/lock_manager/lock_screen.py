import tkinter as tk
import sys
import os

class Screen:
    def __init__(self):
        self.root = None

    def create_lock_screen(self):
        self.root = tk.Tk()
        
        # Make it full screen
        self.root.attributes("-fullscreen", True)
        # Keep it on top of all other windows
        self.root.attributes("-topmost", True)
        # Remove the 'X' and minimize buttons
        self.root.overrideredirect(True)
        self.root.configure(bg='black')

        # Main container to center content
        main_frame = tk.Frame(self.root, bg='black')
        main_frame.place(relx=0.5, rely=0.5, anchor='center')

        label = tk.Label(
            main_frame, 
            text="DEVICE LOCKED", 
            font=("Helvetica", 48, "bold"), 
            fg="white", 
            bg="black"
        )
        label.pack(pady=20)

        sub_label = tk.Label(
            main_frame, 
            text="Your screen time for this session has ended.\nPlease contact your parent to unlock.", 
            font=("Helvetica", 18), 
            fg="#cccccc", 
            bg="black"
        )
        sub_label.pack(pady=10)

        # Prevent closing with Alt+F4
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Re-assert topmost periodically to prevent Task Manager bypass
        def maintain_topmost():
            if self.root:
                self.root.attributes("-topmost", True)
                self.root.lift()
                self.root.after(100, maintain_topmost)
        
        maintain_topmost()

        # Add usage log display
        log_frame = tk.Frame(self.root, bg='black')
        log_frame.pack(side='bottom', fill='x', pady=20)
        
        log_label = tk.Label(
            log_frame,
            text="Recent Activity:",
            font=("Helvetica", 14, "bold"),
            fg="#888888",
            bg="black"
        )
        log_label.pack()

        self.usage_text = tk.Text(
            log_frame,
            height=5,
            width=80,
            font=("Consolas", 10),
            fg="#00FF00",
            bg="black",
            borderwidth=0,
            highlightthickness=0
        )
        self.usage_text.pack(pady=5)
        self.usage_text.config(state='disabled')

        def update_logs():
            if not self.root:
                return
            try:
                import os
                from pathlib import Path
                log_path = Path(os.getenv('APPDATA')) / "Warden" / "usage_display.log"
                if log_path.exists():
                    with open(log_path, "r") as f:
                        lines = f.readlines()
                        # Show last 5 lines
                        last_lines = "".join(lines[-5:])
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

if __name__ == "__main__":
    s = Screen()
    s.create_lock_screen()

