const MAX_ITERATIONS = 500;
const chartForm = document.getElementById('chart-form');
const epsInput = document.getElementById('chart-eps');
const chartCanvas = document.getElementById('cos-chart');
const seriesTableBody = document.querySelector('#series-table tbody');
let cosChart = null;

function seriesCos(x, eps) {
    let term = 1;
    let sum = 0;
    let n = 0;
    while (n < MAX_ITERATIONS && Math.abs(term) >= eps) {
        sum += term;
        n += 1;
        term *= -x * x / ((2 * n - 1) * (2 * n));
    }
    return { value: sum, n };
}

function calculateRows(eps) {
    const rows = [];
    for (let x = -6; x <= 6; x += 0.5) {
        const { value, n } = seriesCos(x, eps);
        rows.push({ x, n, series: value, math: Math.cos(x) });
    }
    return rows;
}

function renderTable(rows, eps) {
    seriesTableBody.replaceChildren(...rows.map((row) => {
        const tableRow = document.createElement('tr');
        [row.x.toFixed(1), row.n, row.series.toFixed(6), row.math.toFixed(6), eps].forEach((value) => {
            const cell = document.createElement('td');
            cell.textContent = value;
            tableRow.append(cell);
        });
        return tableRow;
    }));
}

const whiteBackground = {
    id: 'whiteBackground',
    beforeDraw(chart) {
        chart.ctx.save();
        chart.ctx.fillStyle = '#ffffff';
        chart.ctx.fillRect(0, 0, chart.width, chart.height);
        chart.ctx.restore();
    },
};

function progressiveAnimation(pointsCount) {
    const delay = 2500 / pointsCount;
    const previousY = (ctx) => {
        if (ctx.type !== 'data' || ctx.index === 0) {
            return ctx.chart.scales.y.getPixelForValue(0);
        }
        return ctx.chart.getDatasetMeta(ctx.datasetIndex).data[ctx.index - 1].getProps(['y'], true).y;
    };
    const pointDelay = (key) => (ctx) => {
        if (ctx.type !== 'data' || ctx[key]) {
            return 0;
        }
        ctx[key] = true;
        return ctx.index * delay;
    };
    return {
        x: { type: 'number', easing: 'linear', duration: delay, from: NaN, delay: pointDelay('xStarted') },
        y: { type: 'number', easing: 'linear', duration: delay, from: previousY, delay: pointDelay('yStarted') },
    };
}

function drawChart(rows, eps) {
    if (cosChart) {
        cosChart.destroy();
    }
    cosChart = new Chart(chartCanvas, {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'F(x) — сумма ряда',
                    data: rows.map((row) => ({ x: row.x, y: row.series })),
                    borderColor: '#e08a00',
                    backgroundColor: '#e08a00',
                    borderWidth: 3,
                    pointRadius: 3,
                    tension: 0.3,
                    order: 2,
                },
                {
                    label: 'Math F(x) = Math.cos(x)',
                    data: rows.map((row) => ({ x: row.x, y: row.math })),
                    borderColor: '#1f6b70',
                    backgroundColor: '#1f6b70',
                    borderWidth: 2,
                    borderDash: [6, 4],
                    pointRadius: 0,
                    tension: 0.3,
                    order: 1,
                },
            ],
        },
        options: {
            maintainAspectRatio: false,
            animation: progressiveAnimation(rows.length),
            interaction: { mode: 'nearest', axis: 'x', intersect: false },
            scales: {
                x: { type: 'linear', min: -6, max: 6, title: { display: true, text: 'x' } },
                y: { suggestedMin: -1.5, suggestedMax: 1.5, title: { display: true, text: 'y' } },
            },
            plugins: {
                title: { display: true, text: 'cos x: разложение в ряд и функция Math.cos', font: { size: 16 } },
                subtitle: { display: true, text: `Точность eps = ${eps}` },
                legend: { position: 'bottom' },
                annotation: {
                    annotations: {
                        axisX: { type: 'line', yMin: 0, yMax: 0, borderColor: '#142026', borderWidth: 1 },
                        axisY: { type: 'line', xMin: 0, xMax: 0, borderColor: '#142026', borderWidth: 1 },
                        maximum: { type: 'point', xValue: 0, yValue: 1, radius: 6, backgroundColor: 'rgba(179, 38, 30, 0.6)' },
                        maximumLabel: {
                            type: 'label',
                            xValue: 0,
                            yValue: 1.3,
                            content: 'Максимум: cos 0 = 1',
                            backgroundColor: 'rgba(255, 176, 32, 0.3)',
                        },
                    },
                },
            },
        },
        plugins: [whiteBackground],
    });
}

function build() {
    const eps = Number(epsInput.value);
    const rows = calculateRows(eps);
    renderTable(rows, eps);
    drawChart(rows, eps);
}

chartForm.addEventListener('submit', (event) => {
    event.preventDefault();
    build();
});

document.getElementById('chart-save').addEventListener('click', () => {
    const link = document.createElement('a');
    link.href = cosChart.toBase64Image('image/png', 1);
    link.download = 'cos-chart.png';
    link.click();
});

build();
