#!/usr/bin/env python3
import sys
import os
import re
import time
import json
import base64
import tempfile
import dotenv
import pyautogui
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLineEdit, QLabel, QSpinBox, QDoubleSpinBox, QPlainTextEdit,
    QFormLayout, QMessageBox, QComboBox
)
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool

from google import genai
from google.genai import types

# ------------------ AutomationTask ------------------
class AutomationTask(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str)
        error = pyqtSignal(str)
        
    def __init__(self, init_text, init_delay, gemini_prompt, gemini_response_delay,
                 x, y, width, height, insertion_x, insertion_y,
                 gemini_model, gemini_temperature, gemini_max_output_tokens, gemini_system_prompt):
        super().__init__()
        self.init_text = init_text
        self.init_delay = init_delay
        self.gemini_prompt = gemini_prompt
        self.gemini_response_delay = gemini_response_delay
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.insertion_x = insertion_x
        self.insertion_y = insertion_y
        self.gemini_model = gemini_model
        self.gemini_temperature = gemini_temperature
        self.gemini_max_output_tokens = gemini_max_output_tokens
        self.gemini_system_prompt = gemini_system_prompt
        
        self.signals = self.Signals()
        self._stop = False

    def stop(self):
        self._stop = True

    @pyqtSlot()
    def run(self):
        try:
            # Switch window and type the initial text.
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return
            pyautogui.write(self.init_text, interval=self.init_delay/1000)
            
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return

            # Take a full screenshot.
            temp_dir = tempfile.gettempdir()
            full_screenshot_path = os.path.join(temp_dir, f"full_screenshot_{time.time()}.png")
            try:
                subprocess.run(
                    ["spectacle", "-b", "-n", "-f", "-o", full_screenshot_path],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.signals.error.emit(f"Full screenshot failed: {e.stderr}")
                return
            except FileNotFoundError:
                self.signals.error.emit("'spectacle' not found. Install for KDE screenshot functionality.")
                return
            
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return

            # Crop the screenshot.
            cropped_screenshot_path = os.path.join(temp_dir, f"cropped_screenshot_{time.time()}.png")
            crop_geometry = f"{self.width}x{self.height}+{self.x}+{self.y}"
            try:
                subprocess.run(
                    ["gm", "convert", full_screenshot_path, "-crop", crop_geometry, "+repage", cropped_screenshot_path],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.signals.error.emit(f"Cropping failed: {e.stderr}")
                return
            except FileNotFoundError:
                self.signals.error.emit("'gm' command not found. Install GraphicsMagick.")
                return

            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return

            # Call the Gemini API using the cropped screenshot.
            gemini_response_text = self.call_gemini_api(cropped_screenshot_path)
            if gemini_response_text.lower().startswith("error"):
                self.signals.error.emit(gemini_response_text)
                return
            
            time.sleep(2)
            if self._stop:
                self.signals.error.emit("Automation stopped by user.")
                return
            # Click at the designated insertion point before typing the Gemini response.
            pyautogui.click(self.insertion_x, self.insertion_y)
            pyautogui.write(gemini_response_text, interval=self.gemini_response_delay/1000)
            self.signals.finished.emit(cropped_screenshot_path)
        except Exception as e:
            self.signals.error.emit(f"Automation Error: {str(e)}")

    def call_gemini_api(self, screenshot_path) -> str:
        try:
            API_KEY = os.environ.get("GEMINI_API_KEY")
            if not API_KEY:
                return "Error: GEMINI_API_KEY not set in environment."
            
            client = genai.Client(api_key=API_KEY)
            with open(screenshot_path, "rb") as f:
                image_bytes = f.read()
            image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            
            response = client.models.generate_content(
                model=self.gemini_model,
                contents=[image_part, self.gemini_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.gemini_system_prompt,
                    temperature=self.gemini_temperature,
                    max_output_tokens=self.gemini_max_output_tokens
                ),
            )
            return response.text if response.text else "No response generated"
        except Exception as e:
            return f"Error calling Gemini API: {str(e)}"

# ------------------ MainWindow ------------------
class MainWindow(QMainWindow):
    CONFIG_FILENAME = ".automation_config.json"

    def __init__(self):
        super().__init__()
        self.selected_region = None
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.insertion_x = None
        self.insertion_y = None
        self.current_task = None
        self.setup_ui()
        self.setup_connections()
        # Populate the Gemini model dropdown from available models and then load config.
        self.populate_model_dropdown()
        self.load_config()

    def setup_ui(self):
        self.setWindowTitle("Automation Controller")
        self.setGeometry(100, 100, 450, 600)
        main_layout = QVBoxLayout()

        # Region selection and insertion point buttons/labels.
        self.select_region_btn = QPushButton("Select Screenshot Region")
        self.region_label = QLabel("No region selected")
        self.region_label.setContentsMargins(2,2,2,2)
        main_layout.addWidget(self.select_region_btn)
        main_layout.addWidget(self.region_label)

        self.select_insertion_point_btn = QPushButton("Select Text Insertion Point")
        self.insertion_point_label = QLabel("No insertion point selected")
        self.insertion_point_label.setContentsMargins(2,2,2,2)
        main_layout.addWidget(self.select_insertion_point_btn)
        main_layout.addWidget(self.insertion_point_label)

        # Form for core options.
        form_layout = QFormLayout()
        self.initial_text_edit = QLineEdit("11115")
        self.initial_delay_spin = QSpinBox()
        self.initial_delay_spin.setRange(10, 10000)
        self.initial_delay_spin.setValue(800)

        self.gemini_prompt_edit = QLineEdit("In 8 words or less, why do you feel this is a positive ad for the platform?")
        self.gemini_response_delay_spin = QSpinBox()
        self.gemini_response_delay_spin.setRange(10, 10000)
        self.gemini_response_delay_spin.setValue(80)

        form_layout.addRow(QLabel("Initial Text:"), self.initial_text_edit)
        form_layout.addRow(QLabel("Initial Delay (ms):"), self.initial_delay_spin)
        form_layout.addRow(QLabel("Gemini Prompt:"), self.gemini_prompt_edit)
        form_layout.addRow(QLabel("Response Delay (ms):"), self.gemini_response_delay_spin)

        # New configuration options for Gemini API.
        # Replace the QLineEdit for model selection with a QComboBox dropdown.
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItem("Loading...", userData=None)
        form_layout.addRow(QLabel("Gemini API Model:"), self.gemini_model_combo)

        self.gemini_temperature_spin = QDoubleSpinBox()
        self.gemini_temperature_spin.setRange(0.0, 2.0)
        self.gemini_temperature_spin.setSingleStep(0.1)
        self.gemini_temperature_spin.setValue(1.0)
        
        self.gemini_max_output_tokens_spin = QSpinBox()
        self.gemini_max_output_tokens_spin.setRange(1, 1000)
        self.gemini_max_output_tokens_spin.setValue(20)
        
        self.system_prompt_textedit = QPlainTextEdit()
        default_system_prompt = (
            "You are an advanced language model designed to evaluate and respond to questions about advertisements. "
            "When presented with a description or query about an ad, analyze it and provide responses based on the following guidelines:\n\n"
            "1. Emotions and Reactions: Explain what might go through someone's mind when viewing the ad and why it might evoke certain feelings.\n"
            "2. Key Descriptive Words: Provide two words that best encapsulate the reaction to the ad, ensuring they are relevant and insightful.\n"
            "3. Appropriateness and Impact: Evaluate whether the ad is suitable for platforms like Facebook or Instagram, and discuss if elements could be offensive, misleading, or inappropriate.\n"
            "4. Deeper Analysis: Consider the advertiser’s image, analyze the prominence and presentation of products in the ad, and reflect on social reactions.\n\n"
            "Your answer should be one sentence, short, and use informal, natural language."
        )
        self.system_prompt_textedit.setPlainText(default_system_prompt)
        self.system_prompt_textedit.setFixedHeight(130)

        form_layout.addRow(QLabel("Gemini Temperature:"), self.gemini_temperature_spin)
        form_layout.addRow(QLabel("Gemini Max Output Tokens:"), self.gemini_max_output_tokens_spin)
        form_layout.addRow(QLabel("System Prompt:"), self.system_prompt_textedit)

        main_layout.addLayout(form_layout)

        # Start automation button.
        self.keystroke_button = QPushButton("Start Automation Sequence")
        main_layout.addWidget(self.keystroke_button)

        # Automation in progress message and Stop button.
        self.in_progress_label = QLabel("Automation in progress...")
        self.in_progress_label.setVisible(False)
        self.stop_button = QPushButton("Stop Automation")
        self.stop_button.setVisible(False)
        main_layout.addWidget(self.in_progress_label)
        main_layout.addWidget(self.stop_button)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def setup_connections(self):
        self.keystroke_button.clicked.connect(self.on_keystroke_button_clicked)
        self.select_region_btn.clicked.connect(self.on_select_region_clicked)
        self.select_insertion_point_btn.clicked.connect(self.on_select_insertion_point_clicked)
        self.stop_button.clicked.connect(self.on_stop_button_clicked)

    def populate_model_dropdown(self):
        try:
            API_KEY = os.environ.get("GEMINI_API_KEY")
            if not API_KEY:
                QMessageBox.critical(self, "Error", "GEMINI_API_KEY not set in environment.")
                return
            client = genai.Client(api_key=API_KEY)
            models = client.models.list()
            # Filter only for Gemini models (i.e. model names that start with "models/gemini-")
            gemini_models = [model for model in models if model.name.startswith("models/gemini-")]
            gemini_models.sort(key=lambda m: m.name)
            self.gemini_model_combo.clear()
            # Populate the dropdown with display_name (and store the model name as userData)
            for model in gemini_models:
                self.gemini_model_combo.addItem(model.display_name, model.name)
            # Set default selection if available.
            default_index = self.gemini_model_combo.findData("models/gemini-2.0-flash")
            if default_index != -1:
                self.gemini_model_combo.setCurrentIndex(default_index)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error retrieving Gemini models: {e}")

    def on_select_region_clicked(self):
        try:
            result = subprocess.run(
                ['slurp'],
                capture_output=True,
                text=True,
                check=True
            )
            self.selected_region = result.stdout.strip()
            match = re.match(r"^(-?\d+),(-?\d+)\s+(-?\d+)x(-?\d+)$", self.selected_region)
            if match:
                self.x, self.y, self.width, self.height = map(int, match.groups())
                self.region_label.setText(f"Selected: {self.selected_region}")
            else:
                QMessageBox.critical(self, "Error", "Invalid region format")
                self.selected_region = None
                self.region_label.setText("Invalid region - select again")
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
            self.x = self.y = self.width = self.height = None

    def on_select_insertion_point_clicked(self):
        try:
            result = subprocess.run(
                ['slurp'],
                capture_output=True,
                text=True,
                check=True
            )
            insertion_region = result.stdout.strip()  # Expected format: "X,Y WxH"
            match = re.match(r"^(-?\d+),(-?\d+)\s+(-?\d+)x(-?\d+)$", insertion_region)
            if match:
                x, y, w, h = map(int, match.groups())
                self.insertion_x = x + w // 2
                self.insertion_y = y + h // 2
                self.insertion_point_label.setText(f"Selected Insertion Point: ({self.insertion_x}, {self.insertion_y})")
            else:
                QMessageBox.critical(self, "Error", "Invalid insertion point format")
                self.insertion_x = self.insertion_y = None
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                QMessageBox.information(self, "Info", "Insertion point selection canceled")
            else:
                QMessageBox.critical(self, "Error", f"Slurp error: {e.stderr}")
            self.insertion_x = self.insertion_y = None
        except FileNotFoundError:
            QMessageBox.critical(self, "Error",
                "'slurp' not found. Install for region/insertion selection:\nsudo apt install slurp")
            self.insertion_x = self.insertion_y = None

    def on_keystroke_button_clicked(self):
        if not self.selected_region or self.x is None or self.insertion_x is None:
            QMessageBox.warning(self, "Warning", "Select screenshot region and insertion point first!")
            return

        # Retrieve the Gemini model from the dropdown.
        gemini_model = self.gemini_model_combo.currentData()
        if not gemini_model:
            QMessageBox.warning(self, "Warning", "Please select a valid Gemini model from the dropdown!")
            return

        # Disable start, show in progress UI.
        self.keystroke_button.setEnabled(False)
        self.in_progress_label.setVisible(True)
        self.stop_button.setVisible(True)

        init_text = self.initial_text_edit.text()
        init_delay = self.initial_delay_spin.value()
        gemini_prompt = self.gemini_prompt_edit.text()
        gemini_response_delay = self.gemini_response_delay_spin.value()
        gemini_temperature = self.gemini_temperature_spin.value()
        gemini_max_output_tokens = self.gemini_max_output_tokens_spin.value()
        gemini_system_prompt = self.system_prompt_textedit.toPlainText()
        
        task = AutomationTask(
            init_text,
            init_delay,
            gemini_prompt,
            gemini_response_delay,
            self.x,
            self.y,
            self.width,
            self.height,
            self.insertion_x,
            self.insertion_y,
            gemini_model,
            gemini_temperature,
            gemini_max_output_tokens,
            gemini_system_prompt
        )
        self.current_task = task
        task.signals.finished.connect(self.on_sequence_finished)
        task.signals.error.connect(self.on_task_error)
        QThreadPool.globalInstance().start(task)

    @pyqtSlot()
    def on_stop_button_clicked(self):
        if self.current_task:
            self.current_task.stop()
            self.stop_button.setEnabled(False)
            self.in_progress_label.setText("Stopping automation...")

    @pyqtSlot(str)
    def on_sequence_finished(self, screenshot_path):
        self.in_progress_label.setVisible(False)
        self.stop_button.setVisible(False)
        self.keystroke_button.setEnabled(True)
        self.current_task = None
        try:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        except Exception as e:
            print(f"Error cleaning up screenshot: {str(e)}")

    @pyqtSlot(str)
    def on_task_error(self, message):
        self.in_progress_label.setVisible(False)
        self.stop_button.setVisible(False)
        self.keystroke_button.setEnabled(True)
        self.current_task = None
        QMessageBox.critical(self, "Error", message)

    def load_config(self):
        if os.path.exists(self.CONFIG_FILENAME):
            try:
                with open(self.CONFIG_FILENAME, "r", encoding="utf8") as f:
                    config = json.load(f)
                self.initial_text_edit.setText(config.get("initial_text", "11115"))
                self.initial_delay_spin.setValue(config.get("initial_delay", 800))
                self.gemini_prompt_edit.setText(config.get("gemini_prompt", 
                    "In 8 words or less, why do you feel this is a positive ad for the platform?"))
                self.gemini_response_delay_spin.setValue(config.get("gemini_response_delay", 80))
                # Update the dropdown selection based on the saved model.
                saved_model = config.get("gemini_model", "models/gemini-2.0-flash")
                index = self.gemini_model_combo.findData(saved_model)
                if index != -1:
                    self.gemini_model_combo.setCurrentIndex(index)
                self.gemini_temperature_spin.setValue(config.get("gemini_temperature", 1.0))
                self.gemini_max_output_tokens_spin.setValue(config.get("gemini_max_output_tokens", 20))
                self.system_prompt_textedit.setPlainText(config.get("system_prompt", self.system_prompt_textedit.toPlainText()))
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        config = {
            "initial_text": self.initial_text_edit.text(),
            "initial_delay": self.initial_delay_spin.value(),
            "gemini_prompt": self.gemini_prompt_edit.text(),
            "gemini_response_delay": self.gemini_response_delay_spin.value(),
            # Save the underlying model name from the dropdown.
            "gemini_model": self.gemini_model_combo.currentData(),
            "gemini_temperature": self.gemini_temperature_spin.value(),
            "gemini_max_output_tokens": self.gemini_max_output_tokens_spin.value(),
            "system_prompt": self.system_prompt_textedit.toPlainText(),
        }
        try:
            with open(self.CONFIG_FILENAME, "w", encoding="utf8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def closeEvent(self, event):
        self.save_config()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dotenv.load_dotenv()  # Load environment variables (for GEMINI_API_KEY)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())