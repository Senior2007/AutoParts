const ageForm = document.getElementById('age-form');
const birthDateInput = document.getElementById('birth-date');
const ageResult = document.getElementById('age-result');

function calculateAge(birthDate, today) {
    let age = today.getFullYear() - birthDate.getFullYear();
    const birthdayNotCome = today.getMonth() < birthDate.getMonth()
        || (today.getMonth() === birthDate.getMonth() && today.getDate() < birthDate.getDate());
    if (birthdayNotCome) {
        age -= 1;
    }
    return age;
}

ageForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const [year, month, day] = birthDateInput.value.split('-').map(Number);
    const birthDate = new Date(year, month - 1, day);
    const today = new Date();
    ageResult.hidden = false;

    if (birthDate > today) {
        ageResult.textContent = 'Дата рождения не может быть в будущем.';
        return;
    }

    const age = calculateAge(birthDate, today);
    if (age >= 18) {
        const weekday = birthDate.toLocaleDateString('ru-RU', { weekday: 'long' });
        ageResult.textContent = `Полных лет: ${age}. День недели вашей даты рождения — ${weekday}.`;
    } else {
        ageResult.textContent = `Полных лет: ${age}. Для использования сайта нужно разрешение родителей.`;
        alert('Вам меньше 18 лет. Для использования сайта необходимо разрешение родителей.');
    }
});
