function renderPagination(container, pageCount, currentPage, onSelect) {
    const createButton = (text, page, disabled) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = text;
        button.disabled = disabled;
        button.addEventListener('click', () => onSelect(page));
        return button;
    };

    const buttons = [createButton('‹ Назад', currentPage - 1, currentPage === 1)];
    for (let page = 1; page <= pageCount; page += 1) {
        const button = createButton(String(page), page, false);
        if (page === currentPage) {
            button.classList.add('active');
            button.setAttribute('aria-current', 'page');
        }
        buttons.push(button);
    }
    buttons.push(createButton('Вперед ›', currentPage + 1, currentPage === pageCount));
    container.replaceChildren(...buttons);
}
