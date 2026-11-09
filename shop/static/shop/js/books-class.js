class Publication {
    #title;
    #year;

    constructor(title, year) {
        this.title = title;
        this.year = year;
    }

    get title() {
        return this.#title;
    }

    set title(title) {
        this.#title = title;
    }

    get year() {
        return this.#year;
    }

    set year(year) {
        this.#year = Number(year);
    }

    getInfo() {
        return `«${this.title}», ${this.year} г.`;
    }
}

class Book extends Publication {
    #author;

    constructor(author, title, year) {
        super(title, year);
        this.author = author;
    }

    get author() {
        return this.#author;
    }

    set author(author) {
        this.#author = author;
    }

    static addFromForm(form, books) {
        const fields = form.elements;
        const book = new Book(fields.author.value.trim(), fields.title.value.trim(), fields.year.value);
        books.push(book);
        form.reset();
        return book;
    }

    static showAll(books, list) {
        list.replaceChildren(...books.map((book) => {
            const item = document.createElement('li');
            item.textContent = `${book.author} — ${book.getInfo()}`;
            return item;
        }));
    }

    static showResult(books, author, output) {
        const titles = books
            .filter((book) => book.author.toLowerCase() === author.toLowerCase() && book.year >= 1980)
            .map((book) => `«${book.title}»`);
        output.hidden = false;
        output.textContent = titles.length
            ? `Книги автора ${author}, изданные с 1980 года: ${titles.join(', ')}.`
            : `Книг автора ${author}, изданных с 1980 года, нет.`;
    }
}
