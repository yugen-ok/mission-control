import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time


class ReloadHandler(FileSystemEventHandler):
    def __init__(self, process_cmd):
        self.process_cmd = process_cmd
        self.process = subprocess.Popen(self.process_cmd)

    def on_any_event(self, event):
        # Kill the current process and restart it with the same arguments
        self.process.terminate()
        self.process = subprocess.Popen(self.process_cmd)


if __name__ == "__main__":
    # Fix: Ensure the script captures all arguments passed after the script name
    parser = argparse.ArgumentParser(description="Watchdog script for auto-restarting main.py")
    parser.add_argument("-m", type=str, help="Mode", default="default")
    parser.add_argument("-ah", action="store_true", help="Some boolean flag")
    parser.add_argument("-hv", action="store_true", help="Another boolean flag")
    args, extra_args = parser.parse_known_args()  # Captures unknown args

    # Construct the command to run main.py with all arguments
    process_cmd = ["python", "main.py"]

    # Add known arguments
    if args.m:
        process_cmd.extend(["-m", args.m])
    if args.ah:
        process_cmd.append("-ah")
    if args.hv:
        process_cmd.append("-hv")

    # Add any extra arguments the user provided
    process_cmd.extend(extra_args)

    print(f"Running: {' '.join(process_cmd)}")

    process = subprocess.Popen(process_cmd)  # Start the app
    event_handler = ReloadHandler(process_cmd)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)  # Watch current directory
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        process.terminate()

    observer.join()
