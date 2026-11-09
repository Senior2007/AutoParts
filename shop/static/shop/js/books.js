const INITIAL_BOOKS = [
    { author: 'Пелевин', title: 'Омон Ра', year: 1992 },
    { author: 'Пелевин', title: 'Чапаев и Пустота', year: 1996 },
    { author: 'Пелевин', title: 'Generation П', year: 1999 },
    { author: 'Стругацкий', title: 'Пикник на обочине', year: 1972 },
    { author: 'Стругацкий', title: 'Град обреченный', year: 1989 },
    { author: 'Булгаков', title: 'Мастер и Маргарита', year: 1967 },
    { author: 'Акунин', title: 'Азазель', year: 1998 },
    { author: 'Улицкая', title: 'Казус Кукоцкого', year: 2001 },
    { author: 'Толстой', title: 'Война и мир', year: 1869 },
];

function setupBooks(sectionId, BookType) {
    const section = document.getElementById(sectionId);
    const list = section.querySelector('[data-role="list"]');
    const result = section.querySelector('[data-role="result"]');
    const books = INITIAL_BOOKS.map((item) => new BookType(item.author, item.title, item.year));

    BookType.showAll(books, list);

    section.querySelector('[data-role="add-form"]').addEventListener('submit', (event) => {
        event.preventDefault();
        BookType.addFromForm(event.target, books);
        BookType.showAll(books, list);
    });

    section.querySelector('[data-role="search-form"]').addEventListener('submit', (event) => {
        event.preventDefault();
        BookType.showResult(books, event.target.elements.author.value.trim(), result);
    });
}

setupBooks('books-prototype', ProtoBook);
setupBooks('books-class', Book);
