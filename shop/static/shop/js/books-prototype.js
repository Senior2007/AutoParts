function ProtoPublication(title, year) {
    this.title = title;
    this.year = Number(year);
}

ProtoPublication.prototype.getTitle = function () {
    return this.title;
};

ProtoPublication.prototype.setTitle = function (title) {
    this.title = title;
};

ProtoPublication.prototype.getYear = function () {
    return this.year;
};

ProtoPublication.prototype.setYear = function (year) {
    this.year = Number(year);
};

ProtoPublication.prototype.getInfo = function () {
    return `«${this.title}», ${this.year} г.`;
};

function ProtoBook(author, title, year) {
    ProtoPublication.call(this, title, year);
    this.author = author;
}

ProtoBook.prototype = Object.create(ProtoPublication.prototype);
ProtoBook.prototype.constructor = ProtoBook;

ProtoBook.prototype.getAuthor = function () {
    return this.author;
};

ProtoBook.prototype.setAuthor = function (author) {
    this.author = author;
};

ProtoBook.addFromForm = function (form, books) {
    const fields = form.elements;
    const book = new ProtoBook(fields.author.value.trim(), fields.title.value.trim(), fields.year.value);
    books.push(book);
    form.reset();
    return book;
};

ProtoBook.showAll = function (books, list) {
    list.replaceChildren(...books.map((book) => {
        const item = document.createElement('li');
        item.textContent = `${book.getAuthor()} — ${book.getInfo()}`;
        return item;
    }));
};

ProtoBook.showResult = function (books, author, output) {
    const titles = books
        .filter((book) => book.getAuthor().toLowerCase() === author.toLowerCase() && book.getYear() >= 1980)
        .map((book) => `«${book.getTitle()}»`);
    output.hidden = false;
    output.textContent = titles.length
        ? `Книги автора ${author}, изданные с 1980 года: ${titles.join(', ')}.`
        : `Книг автора ${author}, изданных с 1980 года, нет.`;
};
