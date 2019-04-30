import sys
import os

from watchdog.observers import Observer


class MyFileSystemEventHand

def start_watch(path, callback):
    observer = Observer()
    observer.schedule()


if __name__ == '__main__':
    argv = sys.argv[1:]
    if not argv:
        print("Usage: ./pymonitor your-script.py")
        exit(0)
    if argv[0] != "python3":
        argv.insert(0, "python3")
    command = argv
    path = os.path.abspath(".")
    start_watch(path, None)