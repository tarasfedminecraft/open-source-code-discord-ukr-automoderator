let currentGuildId = null;

async function loadGuild(guildId, guildName, hasBot) {
    if (!hasBot) {
        // Якщо бота немає, перекидаємо на додавання
        window.open(`https://discord.com/api/oauth2/authorize?client_id=1462416328815022203&permissions=8&scope=bot%20applications.commands&guild_id=${guildId}`, '_blank');
        return;
    }

    currentGuildId = guildId;
    document.querySelector('.empty-state').style.display = 'none';
    const settingsArea = document.getElementById('settings-area');
    settingsArea.style.display = 'block';
    document.getElementById('server-title').innerText = `Налаштування: ${guildName}`;

    // Анімація завантаження
    settingsArea.style.opacity = '0.5';

    try {
        const response = await fetch(`/api/get_all_data/${guildId}`);
        if(response.ok) {
            const data = await response.json();
            fillData(data);
        } else {
            alert("Помилка доступу або ви не адмін!");
        }
    } catch (e) {
        console.error(e);
    }

    settingsArea.style.opacity = '1';
}

function fillData(data) {
    // Anti Invite
    document.getElementById('ai-enabled').checked = data.anti_invite.enabled === 1;

    // Anti TLauncher
    document.getElementById('at-enabled').checked = data.anti_tl.enabled === 1;
    document.getElementById('at-warns').value = data.anti_tl.warnings_to_ban || 3;

    // Games
    document.getElementById('count-num').value = data.counting.current_count || 0;
    document.getElementById('count-chan').value = data.server.counting_channel || "";
}

// Функція оновлення налаштувань
async function updateDB(table, field, value) {
    if (!currentGuildId) return;

    // Якщо value це чекбокс (true/false) конвертуємо в 1/0
    const valToSend = typeof value === 'boolean' ? (value ? 1 : 0) : value;

    await fetch('/api/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            guild_id: currentGuildId,
            table: table,
            field: field,
            value: valToSend
        })
    });
}

// Окрема функція для користувачів
async function updateUserEco() {
    const userId = document.getElementById('eco-user-id').value;
    const amount = document.getElementById('eco-amount').value;
    if(!userId || !amount) return alert("Заповніть поля!");

    await fetch('/api/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            guild_id: currentGuildId,
            table: 'users',
            field: 'balance', // Припускаємо що поле балансу називається balance
            value: amount,
            target_user_id: userId
        })
    });
    alert("Баланс оновлено!");
}

function switchTab(tabName) {
    // Ховаємо всі контент блоки
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    // Знімаємо активність з кнопок
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    // Активуємо потрібне
    document.getElementById(`tab-${tabName}`).classList.add('active');
    event.currentTarget.classList.add('active');
}