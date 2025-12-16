from kernel import run_agent
import sys

if __name__ == "__main__":
    # Get device serial from command line argument
    if len(sys.argv) < 2:
        print("Usage: python apple-music-test.py <device_serial>")
        exit(1)
    device_serial = sys.argv[1]

    goal="Open Apple Music app and start play any song"
    run_agent(goal, device_serial)