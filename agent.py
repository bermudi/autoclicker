import sys
import os
import re
import time
import base64
import tempfile
import dotenv
import pyautogui
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLineEdit, QLabel, QSpinBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
import google as genai

class AutomationTask(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str)
        error = pyqtSignal(str)

    def __init__(self, init_text, init_delay, gemini_prompt, gemini_response_delay, region):
        super().__init__()
        self.init_text = init_text
        self.init_delay = init_delay
        self.gemini_prompt = gemini_prompt
        self.gemini_response_delay = gemini_response_delay
        self.region = region
        self.signals = self.Signals()

    @pyqtSlot()
    def run(self):
        try:
            # Switch to active window with focus delay
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)  # Allow window focus stabilization

            # Type initial text with delay
            pyautogui.write(self.init_text, interval=self.init_delay/1000)
            
            # Generate unique temporary file path
            screenshot_path = os.path.join(
                tempfile.gettempdir(),
                f"screenshot_{time.time()}.png"
            )
            
            # Take screenshot using spectacle
            try:
                result = subprocess.run(
                    ['spectacle', '-b', '-r', '-o', screenshot_path],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                self.signals.error.emit(f"Screenshot failed: {e.stderr}")
                return
            except FileNotFoundError:
                self.signals.error.emit("'spectacle' not found. Install for KDE screenshot functionality.")
                return
            
            # Get Gemini response
            gemini_response_text = self.call_gemini_api(screenshot_path)
            if gemini_response_text.startswith("Error:"):
                self.signals.error.emit(gemini_response_text)
                return
            
            # Wait for user to focus response field
            time.sleep(2)
            
            # Type Gemini response with delay
            pyautogui.write(gemini_response_text, interval=self.gemini_response_delay/1000)
            
            self.signals.finished.emit(screenshot_path)
        except Exception as e:
            self.signals.error.emit(f"Automation Error: {str(e)}")

    def call_gemini_api(self, screenshot_path) -> str:
        try:
            API_KEY = os.environ.get("GEMINI_API_KEY")
            if not API_KEY:
                return "Error: GEMINI_API_KEY not set in environment."
            
            genai.configure(api_key=API_KEY)
            
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            model = genai.GenerativeModel(model_name="gemini-1.5-flash")
            response = model.generate_content([
                {"mime_type": "image/png", "data": image_data},
                self.gemini_prompt
            ])
            
            return response.text if response.text else "No response generated"
        except Exception as e:
            return f"Error calling Gemini API: {str(e)}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_region = None
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        self.setWindowTitle("Automation Controller")
        self.setGeometry(100, 100, 450, 400)
        
        main_layout = QVBoxLayout()
        
        # Region selection components
        self.select_region_btn = QPushButton("Select Screenshot Region")
        self.region_label = QLabel("No region selected")
        main_layout.addWidget(self.select_region_btn)
        main_layout.addWidget(self.region_label)

        # Configuration form
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

        self.keystroke_button = QPushButton("Start Automation Sequence")
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.keystroke_button)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_connections(self):
        self.keystroke_button.clicked.connect(self.on_keystroke_button_clicked)
        self.select_region_btn.clicked.connect(self.on_select_region_clicked)

    def on_select_region_clicked(self):
        """Handle region selection using slurp"""
        try:
            result = subprocess.run(
                ['slurp'],
                capture_output=True,
                text=True,
                check=True
            )
            self.selected_region = result.stdout.strip()
            
            # Validate region format
            if not re.match(r"^\d+,\d+ \d+x\d+$", self.selected_region):
                QMessageBox.critical(self, "Error", "Invalid region format")
                self.selected_region = None
                self.region_label.setText("Invalid region - select again")
                return
                
            self.region_label.setText(f"Selected: {self.selected_region}")
            
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                QMessageBox.information(self, "Info", "Region selection canceled")
            else:
                QMessageBox.critical(self, "Error", f"Slurp error: {e.stderr}")
            self.selected_region = None
            self.region_label.setText("Selection failed - try again")
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", 
                "'slurp' not found. Install for region selection:\nsudo apt install slurp")
            self.selected_region = None

    def on_keystroke_button_clicked(self):
        """Start automation task with validation"""
        if not self.selected_region:
            QMessageBox.warning(self, "Warning", "Select screenshot region first!")
            return

        init_text = self.initial_text_edit.text()
        init_delay = self.initial_delay_spin.value()
        gemini_prompt = self.gemini_prompt_edit.text()
        gemini_response_delay = self.gemini_response_delay_spin.value()

        task = AutomationTask(
            init_text,
            init_delay,
            gemini_prompt,
            gemini_response_delay,
            self.selected_region
        )
        task.signals.finished.connect(self.on_sequence_finished)
        task.signals.error.connect(self.on_error)
        QThreadPool.globalInstance().start(task)

    @pyqtSlot(str)
    def on_sequence_finished(self, screenshot_path):
        QMessageBox.information(self, "Success", "Automation sequence completed!")
        try:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except Exception as e:
            print(f"Error cleaning up screenshot: {str(e)}")

    @pyqtSlot(str)
    def on_error(self, message):
        QMessageBox.critical(self, "Error", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())