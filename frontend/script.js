document.getElementById("run-btn").addEventListener("click", async () => {
  const code = document.getElementById("code").value;

  // clear old output
  document.getElementById("stdout").textContent = "";
  document.getElementById("stderr").textContent = "";
  document.getElementById("stats").textContent = "";

  try {
    const response = await fetch("http://127.0.0.1:8000/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      document.getElementById("stderr").textContent = `Error ${response.status}: ${response.statusText}`;
      return;
    }

    const data = await response.json();

    document.getElementById("stdout").textContent = data.stdout || "";
    document.getElementById("stderr").textContent = data.stderr || "";
    document.getElementById("stats").textContent =
  `Time: ${data.time_ms ?? "?"} ms\nMemory: ${data.memory_kb ?? "?"} KB`;

  } catch (err) {
    document.getElementById("stderr").textContent = "Server error: " + err.message;
  }
});
