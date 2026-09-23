// Vanilla-JS airport typeahead. Bind to a visible text input (for searching
// by city/airport name, Korean or English) + a hidden input that carries the
// actual IATA code the form submits.
function initAirportPicker(searchInputId, hiddenInputId, listId) {
  const searchInput = document.getElementById(searchInputId);
  const hiddenInput = document.getElementById(hiddenInputId);
  const list = document.getElementById(listId);
  if (!searchInput || !hiddenInput || !list) return;

  let debounceTimer = null;
  let activeIndex = -1;

  function closeList() {
    list.innerHTML = "";
    list.style.display = "none";
    activeIndex = -1;
  }

  function selectItem(item) {
    hiddenInput.value = item.iata;
    searchInput.value = item.label.split(" — ")[0];
    closeList();
  }

  function render(items) {
    list.innerHTML = "";
    if (!items.length) {
      closeList();
      return;
    }
    items.forEach((item, i) => {
      const li = document.createElement("li");
      li.textContent = item.label;
      li.dataset.index = i;
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        selectItem(item);
      });
      list.appendChild(li);
    });
    list.style.display = "block";
  }

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim();
    hiddenInput.value = "";

    // A bare 3-letter code can be typed and used directly without picking
    // from the dropdown.
    if (/^[A-Za-z]{3}$/.test(query)) {
      hiddenInput.value = query.toUpperCase();
    }

    clearTimeout(debounceTimer);
    if (query.length < 1) {
      closeList();
      return;
    }
    debounceTimer = setTimeout(() => {
      fetch(`/api/airports?q=${encodeURIComponent(query)}`)
        .then((r) => r.json())
        .then((items) => render(items))
        .catch(() => closeList());
    }, 200);
  });

  searchInput.addEventListener("keydown", (e) => {
    const items = list.querySelectorAll("li");
    if (!items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      items[activeIndex].dispatchEvent(new Event("mousedown"));
      return;
    } else {
      return;
    }
    items.forEach((li, i) => li.classList.toggle("active", i === activeIndex));
  });

  searchInput.addEventListener("blur", () => setTimeout(closeList, 150));
}
