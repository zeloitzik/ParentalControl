import os
import subprocess
from pathlib import Path

def main():
    project_root = Path(__file__).resolve().parent.parent
    src_dir = project_root / "src"
    dist_dir = project_root / "dist" / "client"
    
    # Ensure dist_dir exists
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    # Paths to source files
    lock_screen_script = src_dir / "warden_client" / "lock_manager" / "lock_screen.py"
    service_script = src_dir / "warden_client" / "service.py"
    
    # We need to set PYTHONPATH so PyInstaller can resolve warden_core
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_dir)

    print(f"--- Building {lock_screen_script.name} ---")
    subprocess.run([
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "lock_screen",
        "--distpath", str(dist_dir),
        str(lock_screen_script)
    ], check=True, env=env)
    
    print(f"\n--- Building {service_script.name} ---")
    subprocess.run([
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--hidden-import", "win32timezone",
        "--hidden-import", "win32serviceutil",
        "--name", "warden_service",
        "--distpath", str(dist_dir),
        str(service_script)
    ], check=True, env=env)
    
    print(f"\nBuild complete! Executables are located in: {dist_dir}")

if __name__ == "__main__":
    main()
