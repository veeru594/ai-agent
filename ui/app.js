const chat = document.getElementById("chat");
const input = document.getElementById("input");
const send = document.getElementById("send");

function addMessage(role, text) {
    const bubble = document.createElement("div");
    bubble.className =
        role === "user"
            ? "bg-blue-600 ml-auto max-w-xl px-4 py-2 rounded-lg"
            : "bg-gray-800 mr-auto max-w-xl px-4 py-2 rounded-lg whitespace-pre-wrap";

    bubble.textContent = text;
    chat.appendChild(bubble);
    chat.scrollTop = chat.scrollHeight;
}

send.onclick = async () => {
    const message = input.value.trim();
    if (!message) return;

    addMessage("user", message);
    input.value = "";

    addMessage("assistant", "Thinking…");

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });

        const data = await res.json();
        // Support both 'reply' (ui v1 spec) and 'response' (legacy) if needed
        // But V1 spec says backend returns {reply: result}
        // We will align backend to this.
        chat.lastChild.textContent = data.reply || data.response;
    } catch (e) {
        chat.lastChild.textContent = "Error: " + e;
        chat.lastChild.classList.add("text-red-400");
    }
};

input.addEventListener("keydown", e => {
    if (e.key === "Enter") send.click();
});
