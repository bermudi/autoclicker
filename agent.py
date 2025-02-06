import sys
import os
import dotenv
import time
import base64
import pyautogui
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLineEdit, QLabel, QSpinBox, QFormLayout
)
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
import google as genai

class AutomationTask(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str)
        error = pyqtSignal(str)

    def __init__(self, init_text, init_delay, gemini_prompt, gemini_response_delay):
        super().__init__()
        self.init_text = init_text
        self.init_delay = init_delay
        self.gemini_prompt = gemini_prompt
        self.gemini_response_delay = gemini_response_delay
        self.signals = self.Signals()

    @pyqtSlot()
    def run(self):
        try:
            # Switch to active window
            pyautogui.hotkey('alt', 'tab')

            # Type initial text with delay
            pyautogui.write(self.init_text, interval=self.init_delay/1000)
            
            # Take screenshot
            screenshot_path = "screenshot.png"
            pyautogui.screenshot(screenshot_path)
            
            # Get Gemini response
            gemini_response_text = self.call_gemini_api(screenshot_path, self.gemini_prompt)
            
            # Wait for user to focus response field
            time.sleep(2)
            
            # Type Gemini response with delay
            pyautogui.write(gemini_response_text, interval=self.gemini_response_delay/1000)
            
            self.signals.finished.emit(screenshot_path)
        except Exception as e:
            self.signals.error.emit(f"Automation Error: {str(e)}")

    def call_gemini_api(self, screenshot_path, gemini_prompt) -> str:
        API_KEY = os.environ.get("GEMINI_API_KEY")
        if not API_KEY:
            return "Error: GEMINI_API_KEY not set in environment."
        genai.configure(api_key=API_KEY)
        system_prompt = """Your system prompt here..."""
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-8b", system_instruction=system_prompt)
        
        try:
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return f"Error reading screenshot: {e}"
            
        full_prompt = [{"mime_type": "image/png", "data": image_data}, gemini_prompt]
        try:
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Error calling Gemini API: {e}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        self.setWindowTitle("Automation Controller")
        self.setGeometry(100, 100, 400, 300)
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.initial_text_edit = QLineEdit("11115")
        self.initial_delay_spin = QSpinBox()
        self.initial_delay_spin.setRange(10, 10000)
        self.initial_delay_spin.setValue(800)
        self.gemini_prompt_edit = QLineEdit("Caption this image.")
        self.gemini_response_delay_spin = QSpinBox()
        self.gemini_response_delay_spin.setRange(10, 10000)
        self.gemini_response_delay_spin.setValue(80)

        form_layout.addRow(QLabel("Initial Text:"), self.initial_text_edit)
        form_layout.addRow(QLabel("Initial Delay (ms):"), self.initial_delay_spin)
        form_layout.addRow(QLabel("Gemini Prompt:"), self.gemini_prompt_edit)
        form_layout.addRow(QLabel("Response Delay (ms):"), self.gemini_response_delay_spin)

        self.keystroke_button = QPushButton("Send Keystrokes and Process with Gemini")
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.keystroke_button)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_connections(self):
        self.keystroke_button.clicked.connect(self.on_keystroke_button_clicked)

    @pyqtSlot()
    def on_keystroke_button_clicked(self):
        init_text = self.initial_text_edit.text()
        init_delay = self.initial_delay_spin.value()
        gemini_prompt = self.gemini_prompt_edit.text()
        gemini_response_delay = self.gemini_response_delay_spin.value()

        task = AutomationTask(init_text, init_delay, gemini_prompt, gemini_response_delay)
        task.signals.finished.connect(self.on_sequence_finished)
        task.signals.error.connect(self.on_error)
        QThreadPool.globalInstance().start(task)

    @pyqtSlot(str)
    def on_sequence_finished(self, screenshot_path):
        print(f"Sequence completed. Screenshot: {screenshot_path}")

    @pyqtSlot(str)
    def on_error(self, message):
        print(f"Error: {message}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())