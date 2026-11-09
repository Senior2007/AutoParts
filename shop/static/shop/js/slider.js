class Slider {
    constructor(element, options = {}) {
        this.element = element;
        this.slides = Array.from(element.querySelectorAll('.slide'));
        this.loop = options.loop ?? true;
        this.navs = options.navs ?? true;
        this.pags = options.pags ?? true;
        this.auto = options.auto ?? false;
        this.stopMouseHover = options.stopMouseHover ?? false;
        this.delay = options.delay || 5;
        this.index = 0;
        this.timer = null;

        this.createControls();
        this.show(0);

        if (this.auto) {
            this.start();
            if (this.stopMouseHover) {
                element.addEventListener('mouseenter', () => this.stop());
                element.addEventListener('mouseleave', () => this.start());
            }
        }
    }

    createControls() {
        this.counter = document.createElement('p');
        this.counter.className = 'slider-counter';
        this.element.append(this.counter);

        if (this.navs) {
            this.prevButton = this.createButton('slider-prev', '‹', 'Предыдущий слайд', () => this.prev());
            this.nextButton = this.createButton('slider-next', '›', 'Следующий слайд', () => this.next());
            this.element.append(this.prevButton, this.nextButton);
        }

        if (this.pags) {
            const pagination = document.createElement('div');
            pagination.className = 'slider-pags';
            this.dots = this.slides.map((slide, index) => {
                const dot = this.createButton('slider-dot', '', `Слайд ${index + 1}`, () => this.show(index));
                pagination.append(dot);
                return dot;
            });
            this.element.append(pagination);
        }
    }

    createButton(className, text, label, handler) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = className;
        button.textContent = text;
        button.setAttribute('aria-label', label);
        button.addEventListener('click', handler);
        return button;
    }

    show(index) {
        this.index = index;
        this.slides.forEach((slide, i) => slide.classList.toggle('active', i === index));
        this.counter.textContent = `${index + 1}/${this.slides.length}`;

        if (this.pags) {
            this.dots.forEach((dot, i) => dot.classList.toggle('active', i === index));
        }
        if (this.navs && !this.loop) {
            this.prevButton.disabled = index === 0;
            this.nextButton.disabled = index === this.slides.length - 1;
        }
    }

    next() {
        if (this.index < this.slides.length - 1) {
            this.show(this.index + 1);
        } else if (this.loop) {
            this.show(0);
        }
    }

    prev() {
        if (this.index > 0) {
            this.show(this.index - 1);
        } else if (this.loop) {
            this.show(this.slides.length - 1);
        }
    }

    start() {
        this.stop();
        this.timer = setInterval(() => this.next(), this.delay * 1000);
    }

    stop() {
        clearInterval(this.timer);
    }
}

const bannerSlider = document.getElementById('banner-slider');

new Slider(bannerSlider, {
    loop: true,
    navs: true,
    pags: true,
    auto: true,
    stopMouseHover: true,
    delay: Number(bannerSlider.dataset.delay),
});
