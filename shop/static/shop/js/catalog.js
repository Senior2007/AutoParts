const catalogRows = Array.from(document.querySelectorAll('#catalog-table tbody tr[itemscope]'));
const pageSizeSelect = document.getElementById('catalog-page-size');
const catalogPagination = document.getElementById('catalog-pagination');

function showCatalogPage(page) {
    const pageSize = Number(pageSizeSelect.value);
    const pageCount = Math.max(1, Math.ceil(catalogRows.length / pageSize));
    const currentPage = Math.min(Math.max(page, 1), pageCount);

    catalogRows.forEach((row, index) => {
        row.hidden = Math.floor(index / pageSize) + 1 !== currentPage;
    });
    renderPagination(catalogPagination, pageCount, currentPage, showCatalogPage);
}

pageSizeSelect.addEventListener('change', () => showCatalogPage(1));
document.getElementById('catalog-pager').hidden = false;
showCatalogPage(1);
