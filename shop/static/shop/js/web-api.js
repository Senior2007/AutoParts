const STORE_POSITION = { latitude: 53.8845, longitude: 27.5615 };
const geoButton = document.getElementById('geo-button');
const geoResult = document.getElementById('geo-result');
const speechForm = document.getElementById('speech-form');
const speechText = document.getElementById('speech-text');
const speechResult = document.getElementById('speech-result');

function distanceKm(from, to) {
    const toRadians = (degrees) => degrees * Math.PI / 180;
    const dLat = toRadians(to.latitude - from.latitude);
    const dLon = toRadians(to.longitude - from.longitude);
    const a = Math.sin(dLat / 2) ** 2
        + Math.cos(toRadians(from.latitude)) * Math.cos(toRadians(to.latitude)) * Math.sin(dLon / 2) ** 2;
    return 6371 * 2 * Math.asin(Math.sqrt(a));
}

geoButton.addEventListener('click', () => {
    if (!('geolocation' in navigator)) {
        geoResult.textContent = 'Браузер не поддерживает геолокацию.';
        return;
    }
    geoResult.textContent = 'Определяем местоположение…';
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const { latitude, longitude, accuracy } = position.coords;
            const distance = distanceKm(position.coords, STORE_POSITION);
            geoResult.textContent = `Широта: ${latitude.toFixed(5)}, долгота: ${longitude.toFixed(5)}, `
                + `точность: ${Math.round(accuracy)} м. До склада AutoParts в Минске: ${distance.toFixed(1)} км.`;
        },
        (error) => {
            geoResult.textContent = `Не удалось определить местоположение: ${error.message}`;
        },
    );
});

speechForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!('speechSynthesis' in window)) {
        speechResult.textContent = 'Браузер не поддерживает синтез речи.';
        return;
    }
    const utterance = new SpeechSynthesisUtterance(speechText.value);
    utterance.lang = 'ru-RU';
    utterance.addEventListener('start', () => {
        speechResult.textContent = 'Идет озвучивание…';
    });
    utterance.addEventListener('end', () => {
        speechResult.textContent = 'Озвучивание завершено.';
    });
    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
});
