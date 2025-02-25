import sys
import time
import pyautogui
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class ClickerThread(QThread):
    update_signal = pyqtSignal(str)
    countdown_signal = pyqtSignal(int, bool)  # seconds, lock_coords

    def __init__(self, interval, num_clicks, button, click_type, lock_coords):
        super().__init__()
        self.interval = interval
        self.num_clicks = num_clicks
        self.button = button
        self.click_type = click_type
        self.lock_coords = lock_coords
        self.running = False
        self.x, self.y = None, None
        self.current_clicks = 0
        self.start_delay = 3

    def run(self):
        self.running = True
        self.current_clicks = 0
        pyautogui.FAILSAFE = False

        # Countdown phase
        for i in range(self.start_delay, 0, -1):
            if not self.running:
                return
            self.countdown_signal.emit(i, self.lock_coords)
            time.sleep(1)

        # Capture position after countdown if needed
        if self.lock_coords:
            self.x, self.y = pyautogui.position()
        else:
            self.x, self.y = None, None

        # Clicking loop
        while self.running:
            click_args = {'button': self.button}
            if self.x is not None and self.y is not None:
                click_args['x'] = self.x
                click_args['y'] = self.y

            if self.click_type == 'double':
                pyautogui.doubleClick(**click_args)
            else:
                pyautogui.click(**click_args)
            
            self.current_clicks += 1
            self.update_signal.emit(f"Clicks performed: {self.current_clicks}")
            
            if self.num_clicks > 0 and self.current_clicks >= self.num_clicks:
                self.stop()
                
            start_time = time.time()
            while time.time() - start_time < self.interval and self.running:
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait()

class AutoClickerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Auto Clicker")
        self.setGeometry(100, 100, 400, 280)

        main_widget = QWidget()
        layout = QVBoxLayout()

        # Click Settings
        settings_layout = QVBoxLayout()

        # Number of clicks
        clicks_layout = QHBoxLayout()
        clicks_layout.addWidget(QLabel("Number of clicks (0 for infinite):"))
        self.clicks_input = QSpinBox()
        self.clicks_input.setRange(0, 99999)
        clicks_layout.addWidget(self.clicks_input)
        settings_layout.addLayout(clicks_layout)

        # Interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (seconds):"))
        self.interval_input = QDoubleSpinBox()
        self.interval_input.setRange(0.1, 1000)
        self.interval_input.setValue(10.0)
        interval_layout.addWidget(self.interval_input)
        settings_layout.addLayout(interval_layout)

        # Button selection
        button_layout = QHBoxLayout()
        button_layout.addWidget(QLabel("Mouse button:"))
        self.button_combo = QComboBox()
        self.button_combo.addItems(["left", "right", "middle"])
        button_layout.addWidget(self.button_combo)
        settings_layout.addLayout(button_layout)

        # Click type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Click type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["single", "double"])
        type_layout.addWidget(self.type_combo)
        settings_layout.addLayout(type_layout)

        # Lock Coordinates
        lock_layout = QHBoxLayout()
        self.lock_checkbox = QCheckBox("Lock Coordinates")
        lock_layout.addWidget(self.lock_checkbox)
        settings_layout.addLayout(lock_layout)

        layout.addLayout(settings_layout)

        # Control buttons
        button_row = QHBoxLayout()
        self.start_stop_btn = QPushButton("Start")
        self.start_stop_btn.clicked.connect(self.toggle_clicking)
        button_row.addWidget(self.start_stop_btn)

        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.close)
        button_row.addWidget(exit_btn)
        layout.addLayout(button_row)

        # Status label
        self.status_label = QLabel("Status: Stopped")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Warning label
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color: red; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.insertWidget(1, self.warning_label)

        # Setup dynamic help
        self.lock_checkbox.stateChanged.connect(self.update_warning_message)
        self.update_warning_message(self.lock_checkbox.checkState().value)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def update_warning_message(self, state):
        if state == Qt.CheckState.Checked.value:
            self.warning_label.setText(
                "After clicking Start:\n"
                "1. Position mouse during 3-second countdown\n"
                "2. Keep mouse still until countdown finishes\n"
                "(Position will be locked automatically)"
            )
        else:
            self.warning_label.setText(
                "After clicking Start:\n"
                "Clicks will use mouse position at each interval\n"
                "You can move mouse freely during operation"
            )

    def toggle_clicking(self):
        if self.thread and self.thread.isRunning():
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        self.start_stop_btn.setText("Stop")
        self.thread = ClickerThread(
            interval=self.interval_input.value(),
            num_clicks=self.clicks_input.value(),
            button=self.button_combo.currentText(),
            click_type=self.type_combo.currentText(),
            lock_coords=self.lock_checkbox.isChecked()
        )
        self.thread.update_signal.connect(self.update_status)
        self.thread.countdown_signal.connect(self.show_countdown)
        self.thread.finished.connect(self.clicking_finished)
        self.thread.start()
        self.status_label.setText("Status: Starting...")

    def stop_clicking(self):
        if self.thread:
            self.thread.stop()
            self.start_stop_btn.setText("Start")
            self.status_label.setText("Status: Stopped")

    def update_status(self, message):
        self.status_label.setText(f"Status: Running - {message}")

    def show_countdown(self, seconds, lock_coords):
        if lock_coords:
            self.status_label.setText(f"Starting in {seconds}... (Keep mouse still!)")
        else:
            self.status_label.setText(f"Starting in {seconds}...")

    def clicking_finished(self):
        self.start_stop_btn.setText("Start")
        self.status_label.setText("Status: Completed")

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoClickerGUI()
    window.show()
    sys.exit(app.exec())