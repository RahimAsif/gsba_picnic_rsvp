function resolveApiBase() {
  const raw = (window.API_BASE || "").trim();
  if (raw && raw !== "undefined" && raw !== "null") {
    return raw.replace(/\/$/, "");
  }

  // Local development fallback
  return "http://localhost:5000/api";
}

const API_BASE = resolveApiBase();

const FOOD_OPTIONS = ["Chicken", "Goat", "Veg/Non-Meat"];
const CHILD_FOOD_OPTIONS = [
  { value: "Chicken", label: "Chicken" },
  { value: "Goat", label: "Goat" },
  { value: "Veg/Non-Meat", label: "Veg/Non-Meat" },
  { value: "Pizza And Nuggets", label: "Pizza and Nuggets" },
];

const adultsInput = document.getElementById("adults");
const adultFoodContainer = document.getElementById("adultFoodContainer");
const childrenInput = document.getElementById("children");
const childAgesContainer = document.getElementById("childAgesContainer");
const emailInput = document.getElementById("email");

emailInput.addEventListener("input", () => {
  emailInput.setCustomValidity("");
});

emailInput.addEventListener("invalid", () => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(emailInput.value.trim())) {
    emailInput.setCustomValidity("Email is not in the correct format.");
  } else {
    emailInput.setCustomValidity("");
  }
});

function renderAdultFoodFields() {
  const count = parseInt(adultsInput.value) || 0;
  adultFoodContainer.innerHTML = "";

  for (let i = 1; i <= count; i++) {
    const wrapper = document.createElement("div");
    wrapper.classList.add("adult-food-group");

    const label = document.createElement("label");
    label.textContent = `Adult ${i} Food Preference`;

    const select = document.createElement("select");
    select.required = true;
    select.classList.add("adult-food");

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Food preference";
    placeholder.disabled = true;
    placeholder.selected = true;
    select.appendChild(placeholder);

    FOOD_OPTIONS.forEach((food) => {
      const option = document.createElement("option");
      option.value = food;
      option.textContent = food;
      select.appendChild(option);
    });

    wrapper.appendChild(label);
    wrapper.appendChild(select);
    adultFoodContainer.appendChild(wrapper);
  }
}

// Dynamically create age fields
childrenInput.addEventListener("input", () => {
  const count = parseInt(childrenInput.value) || 0;
  childAgesContainer.innerHTML = "";

  for (let i = 1; i <= count; i++) {
    const wrapper = document.createElement("div");
    wrapper.classList.add("child-entry-row");

    const childLabel = document.createElement("span");
    childLabel.classList.add("child-entry-label");
    childLabel.textContent = `Child ${i}`;

    const ageInput = document.createElement("input");
    ageInput.type = "number";
    ageInput.min = "0";
    ageInput.max = "19";
    ageInput.required = true;
    ageInput.classList.add("child-age");
    ageInput.placeholder = "Age";
    ageInput.setAttribute("aria-label", `Age of Child ${i}`);

    const foodSelect = document.createElement("select");
    foodSelect.required = true;
    foodSelect.classList.add("child-food");
    foodSelect.setAttribute("aria-label", `Food preference of Child ${i}`);

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Food preference";
    placeholder.disabled = true;
    placeholder.selected = true;
    foodSelect.appendChild(placeholder);

    CHILD_FOOD_OPTIONS.forEach((food) => {
      const option = document.createElement("option");
      option.value = food.value;
      option.textContent = food.label;
      foodSelect.appendChild(option);
    });

    wrapper.appendChild(childLabel);
    wrapper.appendChild(ageInput);
    wrapper.appendChild(foodSelect);

    childAgesContainer.appendChild(wrapper);
  }
});

adultsInput.addEventListener("input", renderAdultFoodFields);

// Render a single RSVP entry into the list
function renderRsvp(rsvp) {
  const li = document.createElement("li");
  li.classList.add("rsvp-row");

  li.innerHTML = `
    <div class="rsvp-name">${rsvp.name}</div>
    <div class="rsvp-stats">
      <span class="pill adults-pill">🧑‍🤝‍🧑 Adults: ${rsvp.adults}</span>
      <span class="pill children-pill">🧒 Children: ${rsvp.children}</span>
    </div>
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
    const childFoodInputs = document.querySelectorAll(".child-food");
    const child_food_preferences = Array.from(childFoodInputs).map(
      (input) => input.value,
    );

    if (child_food_preferences.length !== children || child_food_preferences.some((v) => !v)) {
      alert("Please select a food preference for each child.");
      return;
    }

    const foodInputs = document.querySelectorAll(".adult-food");
    const adult_food_preferences = Array.from(foodInputs).map(
      (input) => input.value,
    );

    if (adult_food_preferences.length !== adults || adult_food_preferences.some((v) => !v)) {
      alert("Please select a food preference for each adult.");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/rsvp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          adults,
          children,
          child_ages,
          child_food_preferences,
          adult_food_preferences,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        alert(data.error || "Failed to submit RSVP.");
        return;
      }

      await loadRsvps();

      document.getElementById("rsvpForm").reset();
      adultFoodContainer.innerHTML = "";
      childAgesContainer.innerHTML = "";

      alert(`Thank you, ${data.rsvp.name}! Your RSVP has been submitted.`);
    } catch (err) {
      alert("Could not connect to server. Please try again.");
      console.error(err);
    }
  });

// Initialize
loadRsvps();
