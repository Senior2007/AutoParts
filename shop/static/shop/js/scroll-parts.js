const road = document.getElementById('road');
const roadParts = Array.from(road.querySelectorAll('.road-part'));

function moveParts() {
    const rect = road.getBoundingClientRect();
    const progress = Math.min(Math.max((window.innerHeight - rect.top) / (window.innerHeight + rect.height), 0), 1);
    const distance = road.clientWidth - roadParts[0].offsetWidth;

    roadParts.forEach((part, index) => {
        const step = Math.min(Math.max(progress * 1.5 - index * 0.125, 0), 1);
        const direction = index % 2 === 0 ? 1 : -1;
        const x = direction === 1 ? step * distance : (1 - step) * distance;
        part.style.transform = `translateX(${x}px) rotate(${direction * step * 720}deg)`;
    });
}

window.addEventListener('scroll', moveParts);
window.addEventListener('resize', moveParts);
moveParts();

const wheel = document.getElementById('rolling-wheel');
const wheelButton = document.getElementById('wheel-toggle');
const wheelAnimation = wheel.animate(
    [
        { left: '0px', transform: 'rotate(0deg)' },
        { left: 'calc(100% - 56px)', transform: 'rotate(720deg)' },
    ],
    { duration: 4000, iterations: Infinity, direction: 'alternate', easing: 'ease-in-out' },
);

wheelButton.addEventListener('click', () => {
    if (wheelAnimation.playState === 'running') {
        wheelAnimation.pause();
        wheelButton.textContent = 'Продолжить';
    } else {
        wheelAnimation.play();
        wheelButton.textContent = 'Пауза';
    }
});
