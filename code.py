import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import requests
import json
import os
import time
import re # Import regular expressions for timestamp parsing
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Constants ---
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_SOURCE_LANG = "auto"
DEFAULT_TARGET_LANG = "zh" # Example: Chinese
DEFAULT_MAX_THREADS = 10
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2 # seconds

# --- Native SRT Handling ---
class Subtitle:
    # ... (Subtitle class remains the same) ...
    def __init__(self, index, start_time, end_time, content):
        self.index = index
        self.start_time = start_time # String format: HH:MM:SS,ms
        self.end_time = end_time   # String format: HH:MM:SS,ms
        self.content = content

    def __str__(self):
        """String representation for composing the file."""
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.content}\n"

class NativeSrtParser:
    """Handles parsing and composing SRT files natively."""

    TIMESTAMP_REGEX = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")

    @staticmethod
    def parse(filepath, log_func=print):
        """
        Parses an SRT file natively, trying multiple common encodings.
        Args:
            filepath (str): Path to the SRT file.
            log_func (callable): Function to use for logging messages (e.g., app.log_message).
        Returns:
            list[Subtitle]: A list of Subtitle objects.
        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If there's a significant parsing error or no suitable encoding is found.
            Exception: For other file reading errors.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Input file not found: {filepath}")

        # --- Encoding Detection Logic ---
        # Encodings to try, in order of preference/likelihood
        # utf-8-sig handles UTF-8 with a BOM (Byte Order Mark)
        # cp1252 is common for Western European languages on Windows
        # latin-1 is similar to cp1252
        # cp1251 for Cyrillic, add others if needed (e.g., 'gbk' for Chinese)
        encodings_to_try = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'cp1251']
        file_content = None
        detected_encoding = None

        for enc in encodings_to_try:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    file_content = f.read()
                detected_encoding = enc
                log_func(f"Successfully read file with encoding: {enc}")
                break # Stop trying once successful
            except UnicodeDecodeError:
                log_func(f"Failed to decode file with encoding: {enc}")
                continue # Try the next encoding
            except FileNotFoundError:
                 raise # Re-raise specific error immediately
            except Exception as e:
                # Catch other potential file reading errors
                raise IOError(f"Error reading file '{filepath}' with encoding {enc}: {e}")

        if file_content is None or detected_encoding is None:
            raise ValueError(f"Could not decode file '{filepath}' with any of the attempted encodings: {encodings_to_try}. Please check the file encoding.")
        # --- End Encoding Detection ---


        subtitles = []
        try:
            # Process the successfully read file_content
            # Replace Windows line endings just in case, then split
            content_normalized = file_content.replace('\r\n', '\n')
            blocks = content_normalized.strip().split('\n\n')

            block_num = 0
            for block in blocks:
                block_num += 1
                block = block.strip()
                if not block:
                    continue

                lines = block.split('\n')

                if len(lines) < 3:
                    log_func(f"Warning: Skipping malformed block #{block_num} (too few lines) near index guess '{lines[0]}...'")
                    continue

                # 1. Parse Index
                try:
                    # Handle potential BOM character if utf-8-sig was used and BOM wasn't fully stripped
                    index_str = lines[0].lstrip('\ufeff')
                    index = int(index_str)
                except ValueError:
                    log_func(f"Warning: Skipping block #{block_num} (invalid index '{lines[0]}')")
                    continue

                # 2. Parse Timestamp
                timestamp_match = NativeSrtParser.TIMESTAMP_REGEX.match(lines[1])
                if not timestamp_match:
                    log_func(f"Warning: Skipping block #{block_num} with index {index} (invalid timestamp format: '{lines[1]}')")
                    continue
                start_time = timestamp_match.group(1)
                end_time = timestamp_match.group(2)

                # 3. Get Content
                content_lines = lines[2:]
                content_text = "\n".join(content_lines).strip()

                subtitles.append(Subtitle(index, start_time, end_time, content_text))

        except Exception as e:
            # This catches errors during the parsing *after* the file has been read
            raise ValueError(f"Error parsing content read from SRT file '{filepath}' (encoding used: {detected_encoding}): {e}")

        return subtitles

    @staticmethod
    def compose(subtitles, filepath, log_func=print):
        """
        Composes a list of Subtitle objects into an SRT file natively, ALWAYS using UTF-8.
        Args:
            subtitles (list[Subtitle]): List of Subtitle objects to write.
            filepath (str): Path to save the output SRT file.
            log_func (callable): Function to use for logging messages.
        Raises:
            Exception: For file writing errors.
        """
        try:
            # Always write output as UTF-8 for maximum compatibility
            with open(filepath, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles):
                    f.write(str(sub.index))
                    f.write('\n')
                    f.write(f"{sub.start_time} --> {sub.end_time}")
                    f.write('\n')
                    f.write(sub.content)
                    f.write('\n')
                    if i < len(subtitles) - 1:
                         f.write('\n')
            log_func(f"Successfully wrote translated file as UTF-8: {filepath}")
        except Exception as e:
            raise ValueError(f"Error writing SRT file '{filepath}' (using UTF-8 encoding): {e}")


# --- Core Translation Logic (Unchanged from previous version) ---

def translate_text_deepseek(text, api_key, source_lang, target_lang, model):
    """Translates a single text string using DeepSeek API with retries."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    if source_lang and source_lang.lower() != 'auto':
        user_prompt = f"Translate the following text from {source_lang} to {target_lang}:\n\n{text}"
    else:
        user_prompt = f"Translate the following text to {target_lang}:\n\n{text}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful subtitle translator."},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
    }

    for attempt in range(RETRY_ATTEMPTS):
        response = None # Initialize response to None
        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                translated_text = result["choices"][0].get("message", {}).get("content", "").strip()
                if translated_text:
                    return translated_text
                else:
                    print(f"Warning: Empty translation received for text: '{text[:50]}...'")
                    return text # Return original on empty translation

            else:
                error_message = f"API Error: Unexpected response format. Response: {result}"
                if attempt < RETRY_ATTEMPTS - 1:
                    print(f"{error_message}. Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise ValueError(error_message)

        except requests.exceptions.RequestException as e:
            error_message = f"Network/API Error: {e}"
            if response is not None:
                 if response.status_code == 401:
                     raise ValueError("Authentication Error: Invalid API Key.")
                 elif response.status_code == 429:
                     error_message += " (Rate limit likely exceeded)"
                 elif response.status_code >= 500:
                     error_message += " (Server error)"

            if attempt < RETRY_ATTEMPTS - 1:
                print(f"{error_message}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise ConnectionError(f"{error_message}. Max retries reached.")
        except Exception as e:
             error_message = f"An unexpected error occurred during translation: {e}"
             if attempt < RETRY_ATTEMPTS - 1:
                print(f"{error_message}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
             else:
                raise RuntimeError(f"{error_message}. Max retries reached.")

    print(f"Warning: Translation failed for text after {RETRY_ATTEMPTS} attempts: '{text[:50]}...'")
    return text # Return original text if all retries fail


# --- GUI Class (Mostly unchanged, but uses NativeSrtParser) ---

class TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepSeek SRT Translator (Native Parser) v1.1") # Version bump
        self.root.geometry("650x550")

        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        # --- Input Frame ---
        input_frame = ttk.LabelFrame(self.root, text="Settings", padding="10")
        input_frame.pack(padx=10, pady=10, fill="x")
        # (API Key, Languages, Max Threads - same as before)
        ttk.Label(input_frame, text="DeepSeek API Key:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(input_frame, textvariable=self.api_key_var, width=40, show="*")
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(input_frame, text="Source Language:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.source_lang_var = tk.StringVar(value=DEFAULT_SOURCE_LANG)
        self.source_lang_entry = ttk.Entry(input_frame, textvariable=self.source_lang_var, width=10)
        self.source_lang_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text="Target Language:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.target_lang_var = tk.StringVar(value=DEFAULT_TARGET_LANG)
        self.target_lang_entry = ttk.Entry(input_frame, textvariable=self.target_lang_var, width=10)
        self.target_lang_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text="Max Threads:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.max_threads_var = tk.IntVar(value=DEFAULT_MAX_THREADS)
        self.max_threads_spinbox = ttk.Spinbox(input_frame, from_=1, to=100, textvariable=self.max_threads_var, width=8)
        self.max_threads_spinbox.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        input_frame.columnconfigure(1, weight=1)

        # --- File Frame ---
        file_frame = ttk.LabelFrame(self.root, text="Files", padding="10")
        file_frame.pack(padx=10, pady=5, fill="x")
        # (Input/Output File selection - same as before)
        ttk.Label(file_frame, text="Input SRT File:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.input_file_var = tk.StringVar()
        self.input_file_entry = ttk.Entry(file_frame, textvariable=self.input_file_var, state="readonly", width=50)
        self.input_file_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_input_btn = ttk.Button(file_frame, text="Browse...", command=self.browse_input)
        self.browse_input_btn.grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(file_frame, text="Output SRT File:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.output_file_var = tk.StringVar()
        self.output_file_entry = ttk.Entry(file_frame, textvariable=self.output_file_var, state="readonly", width=50)
        self.output_file_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.browse_output_btn = ttk.Button(file_frame, text="Save As...", command=self.browse_output)
        self.browse_output_btn.grid(row=1, column=2, padx=5, pady=5)
        file_frame.columnconfigure(1, weight=1)

        # --- Progress Bar ---
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(padx=10, pady=5, fill="x")

        # --- Start Button ---
        self.start_button = ttk.Button(self.root, text="Start Translation", command=self.start_translation_thread)
        self.start_button.pack(padx=10, pady=10)

        # --- Log Area ---
        log_frame = ttk.LabelFrame(self.root, text="Log", padding="10")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state="disabled", font=("Consolas", 9)) # Monospaced font
        self.log_area.pack(fill="both", expand=True)

        # --- Queues for Thread Communication ---
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()

        # Start checking the queues
        self.root.after(100, self.process_log_queue)
        self.root.after(100, self.process_progress_queue)

    # --- GUI Helper Methods (log, progress, browse, set_ui_state - same as before) ---
    def log_message(self, message):
        """Adds a message to the log area (thread-safe)."""
        self.log_queue.put(message)

    def update_progress(self, value):
        """Updates the progress bar (thread-safe)."""
        self.progress_queue.put(value)

    def process_log_queue(self):
        """Processes messages from the log queue in the main thread."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_area.config(state="normal")
                self.log_area.insert(tk.END, message + "\n")
                self.log_area.see(tk.END) # Scroll to the bottom
                self.log_area.config(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_log_queue) # Reschedule

    def process_progress_queue(self):
        """Processes progress updates from the progress queue."""
        try:
            while True:
                 value = self.progress_queue.get_nowait()
                 self.progress_var.set(value)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_progress_queue) # Reschedule

    def browse_input(self):
        filepath = filedialog.askopenfilename(
            title="Select Input SRT File",
            filetypes=(("SRT files", "*.srt"), ("All files", "*.*"))
        )
        if filepath:
            self.input_file_var.set(filepath)
            if not self.output_file_var.get():
                base, ext = os.path.splitext(filepath)
                target_lang = self.target_lang_var.get() or DEFAULT_TARGET_LANG
                suggested_output = f"{base}_{target_lang}{ext}"
                self.output_file_var.set(suggested_output)

    def browse_output(self):
        filepath = filedialog.asksaveasfilename(
            title="Save Translated SRT File As",
            filetypes=(("SRT files", "*.srt"), ("All files", "*.*")),
            defaultextension=".srt",
            initialfile=os.path.basename(self.output_file_var.get() or "translated.srt")
        )
        if filepath:
            self.output_file_var.set(filepath)

    def set_ui_state(self, enabled):
        """Enable or disable UI elements during processing."""
        state = tk.NORMAL if enabled else tk.DISABLED
        readonly_state = tk.NORMAL if enabled else 'readonly' # Keep readable

        self.browse_input_btn.config(state=state)
        self.browse_output_btn.config(state=state)
        self.start_button.config(state=state)
        self.api_key_entry.config(state=readonly_state)
        self.source_lang_entry.config(state=readonly_state)
        self.target_lang_entry.config(state=readonly_state)
        self.max_threads_spinbox.config(state=readonly_state)
        # File entries remain readonly always
        # self.input_file_entry.config(state=readonly_state)
        # self.output_file_entry.config(state=readonly_state)

    # --- Translation Trigger ---
    def start_translation_thread(self):
        """Validates inputs and starts the translation in a separate thread."""
        api_key = self.api_key_var.get()
        input_file = self.input_file_var.get()
        output_file = self.output_file_var.get()
        source_lang = self.source_lang_var.get() or DEFAULT_SOURCE_LANG
        target_lang = self.target_lang_var.get() or DEFAULT_TARGET_LANG
        max_threads = self.max_threads_var.get()

        # Validation (same as before)
        if not api_key:
            messagebox.showerror("Error", "Please enter your DeepSeek API Key.")
            return
        if not input_file: # Check only if it's set, existence checked in run_translation
            messagebox.showerror("Error", "Please select an input SRT file.")
            return
        if not output_file:
            messagebox.showerror("Error", "Please specify an output SRT file path.")
            return
        if not target_lang:
             messagebox.showerror("Error", "Please specify a target language.")
             return
        if max_threads <= 0:
             messagebox.showerror("Error", "Max threads must be greater than 0.")
             return

        # Disable UI, Clear Log, Reset Progress
        self.set_ui_state(False)
        self.log_area.config(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state="disabled")
        self.progress_var.set(0)

        # Start background thread
        thread = threading.Thread(
            target=self.run_translation,
            args=(api_key, input_file, output_file, source_lang, target_lang, max_threads),
            daemon=True
        )
        thread.start()

    # --- Main Translation Logic in Thread ---
    def run_translation(self, api_key, input_file, output_file, source_lang, target_lang, max_threads):
        """The actual translation logic executed in the background thread."""
        try:
            self.log_message(f"Starting translation...")
            self.log_message(f"Input: {input_file}")
            self.log_message(f"Output: {output_file}")
            self.log_message(f"Source Lang: {source_lang}, Target Lang: {target_lang}")
            self.log_message(f"Max Threads: {max_threads}")
            self.log_message(f"Using Native SRT Parser.")
            self.log_message("-" * 20)

            start_time = time.time()

            # 1. Parse SRT using Native Parser
            self.log_message("Parsing input SRT file...")
            # Pass self.log_message so parser warnings appear in the GUI log
            subtitles = NativeSrtParser.parse(input_file, self.log_message)
            total_subs = len(subtitles)
            if total_subs == 0:
                 self.log_message("Input file parsed successfully, but contains no subtitle entries.")
                 self.finish_translation(start_time, 0, 0, True)
                 return

            self.log_message(f"Parsed {total_subs} subtitle entries.")

            translated_subtitles = [None] * total_subs # Pre-allocate list
            processed_count = 0
            error_count = 0

            # 2. Translate using ThreadPoolExecutor
            self.log_message(f"Translating using up to {max_threads} concurrent threads...")
            futures_map = {}
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                # Submit tasks
                for i, sub in enumerate(subtitles):
                    # Use the attributes from our Subtitle class
                    if not sub.content: # Check if content is empty string
                        self.log_message(f"Skipping empty subtitle #{sub.index}")
                        translated_subtitles[i] = Subtitle( # Use our class
                            index=sub.index,
                            start_time=sub.start_time,
                            end_time=sub.end_time,
                            content="" # Keep it empty
                        )
                        processed_count += 1
                        self.update_progress((processed_count / total_subs) * 100)
                        continue

                    future = executor.submit(translate_text_deepseek,
                                             sub.content,
                                             api_key,
                                             source_lang,
                                             target_lang,
                                             DEFAULT_MODEL)
                    futures_map[future] = i # Map future to original index

                # Process completed futures
                for future in as_completed(futures_map):
                    index = futures_map[future]
                    original_sub = subtitles[index]
                    try:
                        translated_text = future.result()
                        translated_subtitles[index] = Subtitle( # Use our class
                            index=original_sub.index,
                            start_time=original_sub.start_time,
                            end_time=original_sub.end_time,
                            content=translated_text
                        )
                    except Exception as e:
                        self.log_message(f"Error translating subtitle #{original_sub.index}: {e}")
                        error_count += 1
                        translated_subtitles[index] = Subtitle( # Use our class
                            index=original_sub.index,
                            start_time=original_sub.start_time,
                            end_time=original_sub.end_time,
                            content=f"[TRANSLATION_ERROR] {original_sub.content}" # Mark error
                        )
                    finally:
                        processed_count += 1
                        self.update_progress((processed_count / total_subs) * 100)


            # Filter out any potential None entries (shouldn't happen with pre-allocation but safe)
            final_subs = [sub for sub in translated_subtitles if sub is not None]

            if not final_subs and total_subs > 0:
                 raise RuntimeError("Translation failed: No subtitles were successfully processed.")
            if len(final_subs) != total_subs:
                 self.log_message(f"Warning: Processed count ({len(final_subs)}) doesn't match initial count ({total_subs}). Check logs.")


            if error_count > 0:
                self.log_message(f"Warning: {error_count} subtitles encountered translation errors.")

            # 3. Save SRT using Native Composer
            self.log_message("Composing translated SRT file...")
            NativeSrtParser.compose(final_subs, output_file, self.log_message)

            self.finish_translation(start_time, total_subs, error_count)

        except FileNotFoundError as e:
             self.log_message(f"\n--- Translation Failed ---")
             self.log_message(f"Error: {e}")
             self.root.after(0, lambda: self.set_ui_state(True))
             self.root.after(0, lambda: messagebox.showerror("File Error", f"Could not find input file:\n{e}"))
        except ValueError as e: # Catch parsing/composing errors
             self.log_message(f"\n--- Translation Failed ---")
             self.log_message(f"Error: {e}")
             self.root.after(0, lambda: self.set_ui_state(True))
             self.root.after(0, lambda: messagebox.showerror("File Processing Error", f"Error processing SRT file:\n{e}"))
        except Exception as e:
            self.log_message(f"\n--- Translation Failed ---")
            self.log_message(f"Error: {e}")
            import traceback
            self.log_message(f"Traceback:\n{traceback.format_exc()}")
            self.root.after(0, lambda: self.set_ui_state(True))
            self.root.after(0, lambda: messagebox.showerror("Translation Failed", f"An unexpected error occurred:\n{e}"))

    # --- Completion Handling (Unchanged) ---
    def finish_translation(self, start_time, total_subs, error_count, success=True):
        """Logs completion message and re-enables UI."""
        end_time = time.time()
        duration = end_time - start_time
        self.log_message("-" * 20)
        if success:
            if total_subs > 0 :
                 success_count = total_subs - error_count
                 self.log_message(f"Translation complete!")
                 self.log_message(f"Processed {total_subs} subtitles ({success_count} successful, {error_count} errors) in {duration:.2f} seconds.")
                 self.log_message(f"Translated file saved to: {self.output_file_var.get()}")
                 if error_count == 0:
                     self.root.after(0, lambda: messagebox.showinfo("Success", f"Translation successful!\nSaved to {self.output_file_var.get()}"))
                 else:
                     self.root.after(0, lambda: messagebox.showwarning("Partial Success", f"Translation finished with {error_count} errors.\nCheck log for details.\nSaved to {self.output_file_var.get()}"))
            else:
                 self.log_message(f"Finished. No valid subtitle entries were found in the input file.")
                 self.root.after(0, lambda: messagebox.showinfo("Finished", "Operation complete. No subtitles found or processed."))

            self.update_progress(100)
        # Re-enable UI (scheduled in main thread)
        self.root.after(0, lambda: self.set_ui_state(True))


# --- Main Execution ---

if __name__ == "__main__":
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()