// table_utils.js
// Utilitários opcionais para filtro/paginação client-side em tabelas

export function filterTable(tableId, query) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    query = query.toLowerCase();
    rows.forEach((row) => {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(query) ? "" : "none";
    });
}

export function paginateTable(tableId, pageSize = 10) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    let currentPage = 1;
    const totalPages = Math.ceil(rows.length / pageSize);

    function showPage(page) {
        rows.forEach((row, i) => {
            const start = (page - 1) * pageSize;
            const end = start + pageSize;
            row.style.display = i >= start && i < end ? "" : "none";
        });
        currentPage = page;
    }

    // cria controles simples
    const nav = document.createElement("div");
    nav.className = "pagination";
    nav.innerHTML = `
    <button id="prevBtn">Anterior</button>
    <span id="pageInfo"></span>
    <button id="nextBtn">Próximo</button>
  `;
    document.querySelector(`#${tableId}`).after(nav);

    function updateNav() {
        document.getElementById(
            "pageInfo"
        ).textContent = `Página ${currentPage}/${totalPages}`;
    }

    nav.querySelector("#prevBtn").addEventListener("click", () => {
        if (currentPage > 1) {
            showPage(currentPage - 1);
            updateNav();
        }
    });
    nav.querySelector("#nextBtn").addEventListener("click", () => {
        if (currentPage < totalPages) {
            showPage(currentPage + 1);
            updateNav();
        }
    });

    showPage(1);
    updateNav();
}
