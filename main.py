import sys
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
                             QComboBox, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pyautogui

class ClickerThread(QThread):
    update_signal = pyqtSignal(str)
    countdown_signal = pyqtSignal(int)

    def __init__(self, interval, num_clicks, button, click_type):
        super().__init__()
        self.interval = interval
        self.num_clicks = num_clicks
        self.button = button
        self.click_type = click_type
        self.running = False
        self.current_clicks = 0
        self.start_delay = 3  # 3-second delay before starting

    def run(self):
        self.running = True
        self.current_clicks = 0
        pyautogui.FAILSAFE = False

        # Countdown before starting
        for i in range(self.start_delay, 0, -1):
            if not self.running:
                return
            self.countdown_signal.emit(i)
            time.sleep(1)

        while self.running:
            if self.click_type == 'double':
                pyautogui.doubleClick(button=self.button)
            else:
                pyautogui.click(button=self.button)

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
        self.interval_input.setRange(0.1, 3600)
        self.interval_input.setValue(1.0)
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
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Add warning label
        self.warning_label = QLabel("After clicking Start:\n1. Don't move mouse for 3 seconds\n2. Keep mouse in desired position")
        self.warning_label.setStyleSheet("color: red; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignCenter)
        layout.insertWidget(1, self.warning_label)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

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
            click_type=self.type_combo.currentText()
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
        self.start_stop_btn.setEnabled(True)
        self.status_label.setText("Status: Stopped")

    def update_status(self, message):
        self.status_label.setText(f"Status: Running - {message}")

    def show_countdown(self, seconds):
        self.status_label.setText(f"Starting in {seconds}... (Keep mouse still!)")

    def clicking_finished(self):
        self.start_stop_btn.setText("Start")
        self.start_stop_btn.setEnabled(True)
        self.status_label.setText("Status: Completed")

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoClickerGUI()
    window.show()
    sys.exit(app.exec_())
