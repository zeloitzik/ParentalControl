import tkinter as tk


class Screen:
    def create_lock_screen():
        root = tk.Tk()
        
        # Make it full screen
        root.attributes("-fullscreen", True)
        
        # Keep it on top of all other windows
        root.attributes("-topmost", True)
        
        # Remove the 'X' and minimize buttons
        root.overrideredirect(True)

        label = tk.Label(root, text="DEVICE LOCKED BY PARENT", font=("Arial", 30), fg="red")
        label.pack(expand=True)

        # prevent closing with Alt+F4
        #root.protocol("WM_DELETE_WINDOW", lambda: None)

        root.mainloop()

