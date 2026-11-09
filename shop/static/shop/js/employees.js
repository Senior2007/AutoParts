const PAGE_SIZE = 3;

const table = document.getElementById('employees-table');
const tableBody = table.querySelector('tbody');
const tableBox = document.getElementById('employees-box');
const preloader = document.getElementById('employees-preloader');
const pagination = document.getElementById('employees-pagination');
const filterForm = document.getElementById('employee-filter');
const filterInput = document.getElementById('employee-filter-input');
const addToggle = document.getElementById('employee-add-toggle');
const employeeForm = document.getElementById('employee-form');
const addButton = document.getElementById('employee-add');
const checkResult = document.getElementById('employee-check');
const photoInput = document.getElementById('new-photo-url');
const phoneInput = document.getElementById('new-phone');
const bonusButton = document.getElementById('employee-bonus');
const bonusText = document.getElementById('employee-bonus-text');
const details = document.getElementById('employee-details');
const detailsBody = document.getElementById('employee-details-body');

const state = {
    employees: [],
    filter: '',
    sortKey: null,
    sortDirection: 1,
    page: 1,
};

function setLoading(isLoading) {
    preloader.hidden = !isLoading;
    tableBox.classList.toggle('loading', isLoading);
}

function runWithPreloader(action) {
    setLoading(true);
    setTimeout(() => {
        action();
        setLoading(false);
    }, 400);
}

function getVisibleEmployees() {
    const query = state.filter.toLowerCase();
    const rows = state.employees.filter((employee) =>
        [employee.full_name, employee.description, employee.phone, employee.email]
            .some((value) => value.toLowerCase().includes(query)),
    );
    if (state.sortKey) {
        rows.sort((a, b) => a[state.sortKey].localeCompare(b[state.sortKey], 'ru') * state.sortDirection);
    }
    return rows;
}

function createCell(content) {
    const cell = document.createElement('td');
    cell.append(content);
    return cell;
}

function createPhoto(employee, size) {
    const photo = document.createElement('img');
    photo.src = employee.photo_url;
    photo.width = size;
    photo.height = size;
    photo.alt = `Фото: ${employee.full_name}`;
    return photo;
}

function createRow(employee) {
    const row = document.createElement('tr');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = employee.selected;
    checkbox.setAttribute('aria-label', `Выбрать: ${employee.full_name}`);
    checkbox.addEventListener('change', () => {
        employee.selected = checkbox.checked;
    });

    const photo = createPhoto(employee, 54);
    photo.className = 'thumb';

    row.append(
        createCell(checkbox),
        createCell(photo),
        createCell(employee.full_name),
        createCell(employee.description),
        createCell(employee.phone),
        createCell(employee.email),
    );
    row.addEventListener('click', (event) => {
        if (event.target !== checkbox) {
            tableBody.querySelectorAll('tr').forEach((item) => item.classList.remove('selected-row'));
            row.classList.add('selected-row');
            showDetails(employee);
        }
    });
    return row;
}

function renderSortMarks() {
    table.querySelectorAll('.sort-button').forEach((button) => {
        const isActive = button.dataset.sort === state.sortKey;
        const ascending = state.sortDirection === 1;
        button.querySelector('.sort-mark').textContent = isActive ? (ascending ? '▲' : '▼') : '⇅';
        button.title = isActive ? `Сортировка ${ascending ? 'по возрастанию' : 'по убыванию'}` : 'Сортировать';
        button.parentElement.setAttribute('aria-sort', isActive ? (ascending ? 'ascending' : 'descending') : 'none');
    });
}

function render() {
    const rows = getVisibleEmployees();
    const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    state.page = Math.min(Math.max(state.page, 1), pageCount);
    const start = (state.page - 1) * PAGE_SIZE;

    tableBody.replaceChildren(...rows.slice(start, start + PAGE_SIZE).map(createRow));
    if (rows.length === 0) {
        const cell = createCell('Сотрудники не найдены.');
        cell.colSpan = 6;
        const row = document.createElement('tr');
        row.append(cell);
        tableBody.append(row);
    }

    renderPagination(pagination, pageCount, state.page, (page) => {
        state.page = page;
        render();
    });
    renderSortMarks();
}

function showDetails(employee) {
    const list = document.createElement('dl');
    [
        ['ФИО', employee.full_name],
        ['Описание работ', employee.description],
        ['Телефон', employee.phone],
        ['Почта', employee.email],
    ].forEach(([title, value]) => {
        const term = document.createElement('dt');
        const description = document.createElement('dd');
        term.textContent = title;
        description.textContent = value;
        list.append(term, description);
    });
    detailsBody.replaceChildren(createPhoto(employee, 120), list);
    details.hidden = false;
}

async function loadEmployees() {
    setLoading(true);
    try {
        const response = await fetch(table.dataset.url);
        const data = await response.json();
        state.employees = data.results.map((employee) => ({ ...employee, selected: false }));
        render();
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="6">Не удалось загрузить данные с сервера.</td></tr>';
    } finally {
        setLoading(false);
    }
}

table.querySelectorAll('.sort-button').forEach((button) => {
    button.addEventListener('click', () => runWithPreloader(() => {
        const key = button.dataset.sort;
        state.sortDirection = state.sortKey === key ? -state.sortDirection : 1;
        state.sortKey = key;
        state.page = 1;
        render();
    }));
});

filterForm.addEventListener('submit', (event) => {
    event.preventDefault();
    runWithPreloader(() => {
        state.filter = filterInput.value.trim();
        state.page = 1;
        render();
    });
});

function validate(url, phone) {
    return {
        url: /^https?:\/\/\S+\.(php|html)$/i.test(url),
        phone: /^(\+375 ?(\(\d{2}\)|\d{2})|8 ?(\(0\d{2}\)|0\d{2})) ?\d{3}[- ]?\d{2}[- ]?\d{2}$/.test(phone),
    };
}

function describe(value, isValid, label, hint) {
    if (value === '') {
        return `${label}: не введен.`;
    }
    return isValid ? `${label}: корректный.` : `${label}: некорректный — ${hint}`;
}

addToggle.addEventListener('click', () => {
    employeeForm.hidden = !employeeForm.hidden;
    addToggle.setAttribute('aria-expanded', String(!employeeForm.hidden));
});

employeeForm.addEventListener('input', () => {
    const url = photoInput.value.trim();
    const phone = phoneInput.value.trim();
    const result = validate(url, phone);

    photoInput.classList.toggle('invalid', url !== '' && !result.url);
    phoneInput.classList.toggle('invalid', phone !== '' && !result.phone);
    checkResult.textContent = [
        describe(url, result.url, 'URL', 'должен начинаться с http:// или https:// и заканчиваться на .php или .html.'),
        describe(phone, result.phone, 'Телефон', 'пример: 80291112233, 8 (029) 1112233, +375 (29) 111-22-33.'),
    ].join('\n');
    checkResult.classList.toggle('ok', result.url && result.phone);

    const allFilled = Array.from(employeeForm.elements)
        .filter((element) => element.name)
        .every((element) => element.value.trim() !== '');
    addButton.disabled = !(allFilled && result.url && result.phone);
});

employeeForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const fields = employeeForm.elements;
    const employee = {
        id: Date.now(),
        full_name: fields.full_name.value.trim(),
        photo_url: fields.photo_url.value.trim(),
        description: fields.description.value.trim(),
        phone: fields.phone.value.trim(),
        email: fields.email.value.trim(),
        selected: false,
    };

    runWithPreloader(() => {
        state.employees.push(employee);
        const position = getVisibleEmployees().indexOf(employee);
        if (position !== -1) {
            state.page = Math.floor(position / PAGE_SIZE) + 1;
        }
        render();
        employeeForm.reset();
        addButton.disabled = true;
        checkResult.classList.remove('ok');
        checkResult.textContent = `Сотрудник ${employee.full_name} добавлен в таблицу.`;
    });
});

bonusButton.addEventListener('click', () => runWithPreloader(() => {
    const surnames = state.employees
        .filter((employee) => employee.selected)
        .map((employee) => employee.full_name.split(' ')[0]);
    bonusText.hidden = false;
    bonusText.textContent = surnames.length
        ? `По итогам месяца премировать сотрудников магазина AutoParts: ${surnames.join(', ')}.`
        : 'Отметьте сотрудников флажками в столбце «Выбор», затем нажмите «Премировать».';
}));

loadEmployees();
