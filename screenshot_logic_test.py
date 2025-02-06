#!/usr/bin/env python3
import subprocess
import sys

def main():
    # Step 1: Take a full-screen screenshot using Spectacle.
    # The options used are:
    #   -b: background mode,
    #   -n: no notification,
    #   -f: fullscreen,
    #   -o: output file.
    screenshot_file = "screenshot.png"
    try:
        subprocess.run(["spectacle", "-b", "-n", "-f", "-o", screenshot_file], check=True)
    except subprocess.CalledProcessError:
        print("Error: Spectacle failed to capture a screenshot.", file=sys.stderr)
        sys.exit(1)

    # Step 2: Use slurp to select a region of the screenshot.
    # When you select a region, slurp outputs a string in the format: "X,Y WxH"
    # For example, "100,200 300x150" where X=100, Y=200, width=300, height=150.
    try:
        slurp_output = subprocess.check_output(["slurp"]).decode("utf-8").strip()
    except subprocess.CalledProcessError:
        print("Error: Slurp did not return a region.", file=sys.stderr)
        sys.exit(1)

    # Parse the geometry string.
    # Expected format: "X,Y WxH"
    parts = slurp_output.split()
    if len(parts) != 2:
        print(f"Unexpected slurp output: {slurp_output}", file=sys.stderr)
        sys.exit(1)

    # Parse X and Y coordinates.
    coords = parts[0].split(',')
    if len(coords) != 2:
        print(f"Unexpected coordinate format: {parts[0]}", file=sys.stderr)
        sys.exit(1)
    try:
        x = int(coords[0])
        y = int(coords[1])
    except ValueError:
        print(f"Unable to parse coordinates: {coords}", file=sys.stderr)
        sys.exit(1)

    # Parse width and height.
    size_parts = parts[1].split('x')
    if len(size_parts) != 2:
        print(f"Unexpected size format: {parts[1]}", file=sys.stderr)
        sys.exit(1)
    try:
        width = int(size_parts[0])
        height = int(size_parts[1])
    except ValueError:
        print(f"Unable to parse size values: {size_parts}", file=sys.stderr)
        sys.exit(1)

    # Prepare the crop geometry for GraphicsMagick.
    # The expected format is "WIDTHxHEIGHT+X+Y".
    crop_geometry = f"{width}x{height}+{x}+{y}"
    print(f"Crop geometry: {crop_geometry}")

    # Step 3: Use GraphicsMagick to crop the screenshot.
    # The gm command below loads the screenshot, crops it using the specified geometry,
    # resets the virtual canvas (+repage), and writes the output to a new file.
    cropped_file = "cropped.png"
    try:
        subprocess.run(
            ["gm", "convert", screenshot_file, "-crop", crop_geometry, "+repage", cropped_file],
            check=True
        )
    except subprocess.CalledProcessError:
        print("Error: gm convert failed to crop the screenshot.", file=sys.stderr)
        sys.exit(1)

    print(f"Cropped screenshot saved as {cropped_file}")


if __name__ == '__main__':
    main()