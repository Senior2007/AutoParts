const FILE_FIELDS_KEY = 'fileFields';
const fileFieldCheckbox = document.getElementById('file-field-add');
const fileFieldsForm = document.getElementById('file-fields');
let fileFields = JSON.parse(localStorage.getItem(FILE_FIELDS_KEY) || '[]');

function saveFileFields() {
    localStorage.setItem(FILE_FIELDS_KEY, JSON.stringify(fileFields));
}

function applyAttributes(input, config) {
    ['name', 'accept', 'capture'].forEach((attribute) => {
        if (config[attribute]) {
            input.setAttribute(attribute, config[attribute]);
        } else {
            input.removeAttribute(attribute);
        }
    });
    input.multiple = config.multiple;
    input.required = config.required;
}

function createFileField(config) {
    const block = document.createElement('fieldset');
    block.className = 'file-field';
    block.innerHTML = `
        <legend>Поле загрузки файла</legend>
        <p><label>Файл <input type="file"></label></p>
        <p><code class="file-code"></code></p>
        <div class="file-settings">
            <label>name <input type="text" data-attribute="name" maxlength="40"></label>
            <label>accept <input type="text" data-attribute="accept" placeholder="image/*,.pdf" maxlength="80"></label>
            <label>capture
                <select data-attribute="capture">
                    <option value="">не задан</option>
                    <option value="user">user — фронтальная камера</option>
                    <option value="environment">environment — основная камера</option>
                </select>
            </label>
            <label><input type="checkbox" data-attribute="multiple"> multiple</label>
            <label><input type="checkbox" data-attribute="required"> required</label>
        </div>
        <button type="button" class="file-remove">Удалить поле</button>`;

    const fileInput = block.querySelector('input[type="file"]');
    const code = block.querySelector('.file-code');

    function update() {
        applyAttributes(fileInput, config);
        code.textContent = fileInput.outerHTML;
    }

    block.querySelectorAll('[data-attribute]').forEach((control) => {
        const attribute = control.dataset.attribute;
        if (control.type === 'checkbox') {
            control.checked = config[attribute];
        } else {
            control.value = config[attribute];
        }
        control.addEventListener('input', () => {
            config[attribute] = control.type === 'checkbox' ? control.checked : control.value.trim();
            update();
            saveFileFields();
        });
    });

    block.querySelector('.file-remove').addEventListener('click', () => {
        fileFields = fileFields.filter((item) => item !== config);
        saveFileFields();
        block.remove();
    });

    update();
    fileFieldsForm.append(block);
}

fileFieldCheckbox.addEventListener('change', () => {
    if (!fileFieldCheckbox.checked) {
        return;
    }
    const config = {
        name: `file${fileFields.length + 1}`,
        accept: '',
        capture: '',
        multiple: false,
        required: false,
    };
    fileFields.push(config);
    saveFileFields();
    createFileField(config);
    fileFieldCheckbox.checked = false;
});

fileFields.forEach(createFileField);
