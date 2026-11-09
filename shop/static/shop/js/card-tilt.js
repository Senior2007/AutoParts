document.querySelectorAll('.product-card').forEach((card) => {
    card.addEventListener('mousemove', (event) => {
        const rect = card.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = `perspective(800px) rotateX(${-y * 18}deg) rotateY(${x * 18}deg) scale(1.04)`;
    });

    card.addEventListener('mouseleave', () => {
        card.style.transform = '';
    });
});
