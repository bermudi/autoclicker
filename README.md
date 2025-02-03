# PyQt Auto Clicker

A flexible and user-friendly auto clicker application built with PyQt6 and PyAutoGUI.

## Features

- Customizable click interval (2-1000 seconds)
- Support for unlimited or fixed number of clicks
- Multiple mouse button options (left, right, middle)
- Single and double click modes
- Coordinate locking capability
- 3-second countdown timer before starting
- Simple and intuitive GUI interface

## Requirements

- Python 3.x
- PyQt6
- PyAutoGUI

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/pyqt-auto-clicker.git
```

2. Install required dependencies:
```bash
pip install PyQt6 pyautogui
```

## Usage

Run the application:
```bash
python main.py
```

### Settings:
- **Number of clicks**: Set to 0 for infinite clicks or specify a number
- **Interval**: Time between clicks (in seconds)
- **Mouse button**: Choose between left, right, or middle mouse button
- **Click type**: Select single or double click
- **Lock Coordinates**: Enable to maintain click position after countdown

### Controls:
- Click "Start" to begin auto-clicking
- Click "Stop" to halt the operation
- Click "Exit" to close the application

## Safety Features

- 3-second countdown before starting to allow proper positioning
- Clear status updates and warnings
- Ability to stop at any time
- Position locking option for precise clicking

## License

MIT License

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
