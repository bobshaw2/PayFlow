document.addEventListener("DOMContentLoaded", () => {
  const search = document.querySelector("#search");
  const filter = document.querySelector("#status-filter");
  const rows = [...document.querySelectorAll("#transactions tbody tr")];
  const empty = document.querySelector("#empty-state");
  function updateTable() {
    const text = search.value.toLowerCase();
    const status = filter.value;
    let visible = 0;
    rows.forEach(row => {
      const show = row.textContent.toLowerCase().includes(text) && (!status || row.dataset.status === status);
      row.hidden = !show;
      if (show) visible += 1;
    });
    empty.hidden = visible !== 0;
  }
  search.addEventListener("input", updateTable);
  filter.addEventListener("change", updateTable);
});
