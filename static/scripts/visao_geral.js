// visao_geral.js — Dashboard Visão Geral
// - gráficos em pizza (Chart.js)
// - legendas brancas
// - chips de turmas dinâmicos
// - render da tabela

const charts = {};
const PALETTE = ["#60a5fa", "#93c5fd", "#a78bfa", "#c4b5fd", "#38bdf8", "#818cf8", "#7dd3fc", "#bfdbfe"];

function upsertPie(id, labels, values, title) {
    const ctx = document.getElementById(id);
    if (!ctx) return;

    const data = {
        labels,
        datasets: [{ label: title, data: values, backgroundColor: PALETTE.slice(0, Math.max(3, values.length)) }]
    };

    const options = {
        responsive: true,
        plugins: {
            legend: {
                position: "bottom",
                labels: { color: "white" } // <- legendas brancas
            },
            tooltip: { enabled: true }
        }
    };

    if (!charts[id]) {
        charts[id] = new Chart(ctx, { type: "pie", data, options });
    } else {
        charts[id].data = data;
        charts[id].update();
    }
}

async function loadData(turma = "") {
    const url = turma ? `/api/visao-geral?turma=${encodeURIComponent(turma)}` : "/api/visao-geral";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // gráficos
    upsertPie("chartDDZ", (data.por_ddz || []).map(x => x.label), (data.por_ddz || []).map(x => x.value), "Por DDZ");
    upsertPie("chartEscola", (data.por_escola || []).map(x => x.label), (data.por_escola || []).map(x => x.value), "Por Escola");
    upsertPie("chartAno", (data.por_ano || []).map(x => x.label), (data.por_ano || []).map(x => x.value), "Por Ano");

    // tabela
    const tbody = document.querySelector("#tabela tbody");
    if (tbody) {
        tbody.innerHTML = "";
        (data.rows || []).forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
        <td>${r.ddz}</td>
        <td>${r.escola}</td>
        <td>${r.professor}</td>
        <td>${r.ano}</td>
        <td>${r.turma}</td>
        <td style="text-align:center;">
          ${r.has_cert ? `<a href="/certificados/${r.cert_id}/download" title="Baixar">📜</a>` : "<span class='muted'>—</span>"}
        </td>`;
            tbody.appendChild(tr);
        });
    }
    const tag = document.getElementById("countTag");
    if (tag) tag.textContent = `${(data.rows || []).length} registro(s)`;
}

/* ---- Chips dinâmicos ----
   Para não depender de nova rota, buscamos /api/visao-geral (sem filtro),
   coletamos as turmas existentes (ex.: "4/2025") e montamos os chips. */
async function buildChips() {
    const wrap = document.getElementById("chips");
    if (!wrap) return;

    // busca uma vez sem filtro para descobrir as turmas existentes
    const res = await fetch("/api/visao-geral");
    if (!res.ok) return;
    const data = await res.json();

    // pega de rows (mais robusto); se vazio, tenta inferir de por_ano + turmas já conhecidas
    const turmasSet = new Set((data.rows || [])
        .map(r => String(r.turma))
        .filter(Boolean));

    // ordena por ano e número (N/ANO)
    const turmas = Array.from(turmasSet).sort((a, b) => {
        const [na, aa] = a.split("/").map(Number);
        const [nb, ab] = b.split("/").map(Number);
        if (aa !== ab) return aa - ab;
        return na - nb;
    });

    // monta HTML
    wrap.innerHTML = "";
    const mk = (label, turma, active = false) => {
        const a = document.createElement("a");
        a.className = "tag" + (active ? " active" : "");
        a.textContent = label;
        if (turma) a.dataset.turma = turma;
        wrap.appendChild(a);
    };
    mk("Todas", "", true);
    turmas.forEach(t => mk(t, t));

    // delegação de clique
    wrap.addEventListener("click", (e) => {
        if (e.target.classList.contains("tag")) {
            wrap.querySelectorAll(".tag").forEach(x => x.classList.remove("active"));
            e.target.classList.add("active");
            loadData(e.target.dataset.turma || "");
        }
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        await buildChips();    // cria os chips existentes
        await loadData();      // carrega visão geral (todas)
    } catch (err) {
        console.error("Dashboard error:", err);
    }

    // Recalcula os gráficos quando a sidebar colapsa/expande (mudança de largura)
    window.addEventListener("resize", () => {
        Object.values(charts).forEach(ch => ch && ch.resize());
    });
});
