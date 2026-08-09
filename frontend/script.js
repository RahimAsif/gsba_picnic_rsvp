function resolveApiBase() {
  const raw = (window.API_BASE || "").trim();
  if (raw && raw !== "undefined" && raw !== "null") {
    return raw.replace(/\/$/, "");
  }

  // Local development fallback
  return "http://localhost:5000/api";
}

const API_BASE = resolveApiBase();

const childrenInput = document.getElementById("children");
const childAgesContainer = document.getElementById("childAgesContainer");

// Dynamically create age fields
childrenInput.addEventListener("input", () => {
  const count = parseInt(childrenInput.value) || 0;
  childAgesContainer.innerHTML = "";

  for (let i = 1; i <= count; i++) {
    const label = document.createElement("label");
    label.textContent = `Age of Child ${i}`;

    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.max = "19";
    input.required = true;
    input.classList.add("child-age");

    childAgesContainer.appendChild(label);
    childAgesContainer.appendChild(input);
  }
});

// Render a single RSVP entry into the list
function renderRsvp(rsvp) {
  const li = document.createElement("li");
  const childrenText =
    rsvp.children > 0
      ? `Children: ${rsvp.children} (${rsvp.children === 1 ? "Age" : "Ages"}: ${rsvp.child_ages.join(", ")})`
      : `Children: 0`;

  li.innerHTML = `
    <strong>${rsvp.name}</strong><br>
    Adults: ${rsvp.adults}<br>
    ${childrenText}
  `;
  document.getElementById("rsvpList").appendChild(li);
}

// Update the summary totals display
function updateSummary(summary) {
  document.getElementById("totalCount").innerHTML = `
    Adults: ${summary.total_adults}<br>
    Children: ${summary.total_children}
  `;
}

// Load existing RSVPs and summary on page load
async function loadRsvps() {
  try {
    const [rsvpsRes, summaryRes] = await Promise.all([
      fetch(`${API_BASE}/rsvps`),
      fetch(`${API_BASE}/summary`),
    ]);

    if (!rsvpsRes.ok || !summaryRes.ok) {
      throw new Error(
        `API request failed (rsvps: ${rsvpsRes.status}, summary: ${summaryRes.status})`,
      );
    }

    const rsvps = await rsvpsRes.json();
    const summary = await summaryRes.json();

    document.getElementById("rsvpList").innerHTML = "";
    rsvps.forEach(renderRsvp);
    updateSummary(summary);
  } catch (err) {
    console.error("Failed to load RSVPs:", err, "API_BASE:", API_BASE);
  }
}

// Submit form
document
  .getElementById("rsvpForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();

    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim().toLowerCase();
    const adults = parseInt(document.getElementById("adults").value);
    const children = parseInt(document.getElementById("children").value) || 0;

    if (adults > 10) {
      alert("You may RSVP up to 10 adults maximum.");
      return;
    }

    const ageInputs = document.querySelectorAll(".child-age");
    const child_ages = Array.from(ageInputs).map((input) =>
      parseInt(input.value),
    );

    try {
      const res = await fetch(`${API_BASE}/rsvp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, adults, children, child_ages }),
      });

      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "Failed to submit RSVP.");
        return;
      }

      renderRsvp(data.rsvp);
      updateSummary(data.summary);

      document.getElementById("rsvpForm").reset();
      childAgesContainer.innerHTML = "";
    } catch (err) {
      alert("Could not connect to server. Please try again.");
      console.error(err);
    }
  });

// Initialize
loadRsvps();
