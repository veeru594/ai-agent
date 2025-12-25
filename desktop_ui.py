import tkinter as tk
from tkinter import scrolledtext, messagebox
from brain.main import handle_request


class JarvisDesktopUI:
    def __init__(self, root):
        self.root = root
        self.root.title("JARVIS")
        self.root.geometry("900x600")
        self.root.configure(bg="#FFFFFF")

        self.code_blocks = []  # store code blocks for copy

        # Chat display
        self.chat_area = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            bg="#0a0a0a",
            fg="#e5e7eb",
            font=("Segoe UI", 10),
            state="disabled"
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Input frame
        input_frame = tk.Frame(root, bg="#020617")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_box = tk.Entry(
            input_frame,
            font=("Consolas", 12),
            bg="#020617",
            fg="#e5e7eb",
            insertbackground="white"
        )
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.input_box.bind("<Return>", self.send_message)
        self.input_box.bind("<Control-Return>", self.send_message)

        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg="#2563eb",
            fg="white",
            font=("Segoe UI", 10),
            width=10
        )
        send_btn.pack(side=tk.RIGHT)

        self._configure_tags()
        self.add_system_message("JARVIS Desktop Online.")

    # ---------------- TAGS ---------------- #

    def _configure_tags(self):
        self.chat_area.tag_config("role_system", foreground="#22c55e", font=("Segoe UI", 9, "bold"))
        self.chat_area.tag_config("role_user", foreground="#38bdf8", font=("Segoe UI", 9, "bold"))
        self.chat_area.tag_config("role_jarvis", foreground="#e5e7eb", font=("Segoe UI", 9, "bold"))

        self.chat_area.tag_config("text", foreground="#e5e7eb", font=("Segoe UI", 10))

        self.chat_area.tag_config(
            "code",
            foreground="#22c55e",
            background="#020617",
            font=("Consolas", 10),
            lmargin1=12,
            lmargin2=12
        )

    # ---------------- MESSAGE HELPERS ---------------- #

    def add_system_message(self, text):
        self._add_simple_message("SYSTEM", text, "role_system")

    def add_user_message(self, text):
        self._add_simple_message("YOU", text, "role_user")

    def add_jarvis_response(self, text):
        self.chat_area.configure(state="normal")
        self.chat_area.insert(tk.END, "JARVIS:\n", "role_jarvis")

        parts = text.split("```")
        for i, part in enumerate(parts):
            if not part.strip():
                continue

            if i % 2 == 0:
                # normal text
                self.chat_area.insert(tk.END, part.strip() + "\n\n", "text")
            else:
                # code block
                code = part.split("\n", 1)
                code_text = code[1] if len(code) > 1 else code[0]
                code_text = code_text.rstrip()

                start_index = self.chat_area.index(tk.END)
                self.chat_area.insert(tk.END, code_text + "\n\n", "code")
                end_index = self.chat_area.index(tk.END)

                self.code_blocks.append(code_text)
                self._insert_copy_button(len(self.code_blocks) - 1, start_index)

        self.chat_area.configure(state="disabled")
        self.chat_area.yview(tk.END)

    def _add_simple_message(self, role, text, role_tag):
        self.chat_area.configure(state="normal")
        self.chat_area.insert(tk.END, f"{role}:\n", role_tag)
        self.chat_area.insert(tk.END, text + "\n\n", "text")
        self.chat_area.configure(state="disabled")
        self.chat_area.yview(tk.END)

    # ---------------- COPY BUTTON ---------------- #

    def _insert_copy_button(self, code_index, position):
        def copy_code():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.code_blocks[code_index])
            messagebox.showinfo("Copied", "Code copied to clipboard.")

        btn = tk.Button(
            self.chat_area,
            text="Copy",
            command=copy_code,
            bg="#1e293b",
            fg="white",
            font=("Segoe UI", 8),
            relief="flat"
        )

        self.chat_area.window_create(position, window=btn)

    # ---------------- SEND ---------------- #

    def send_message(self, event=None):
        message = self.input_box.get().strip()
        if not message:
            return

        self.input_box.delete(0, tk.END)
        self.add_user_message(message)

        result = handle_request(message)
        response_text = result.get("response", "")

        self.add_jarvis_response(response_text)


if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisDesktopUI(root)
    root.mainloop()
