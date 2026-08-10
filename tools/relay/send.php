<?php
/**
 * Приёмник заявок с сайта.
 *
 * Форма шлёт сюда JSON, скрипт кладёт заявку владельцу в MAX и дублирует
 * на почту. Токен бота лежит рядом, в config.php, и в браузер не попадает —
 * именно ради этого приёмник и нужен: если положить токен в страницу,
 * его прочитает любой желающий и завалит владельца спамом.
 *
 * Кладётся в ту же папку, что и index.html. Настройки — в config.php.
 */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

function fail(string $msg, int $code = 400): never
{
    http_response_code($code);
    echo json_encode(['ok' => false, 'error' => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    fail('только POST', 405);
}

$configPath = __DIR__ . '/config.php';
if (!is_file($configPath)) {
    fail('приёмник не настроен', 500);
}
$cfg = require $configPath;

// ---- Читаем заявку -------------------------------------------------------
$raw = file_get_contents('php://input') ?: '';
$data = json_decode($raw, true);
if (!is_array($data)) {
    $data = $_POST;                      // на случай обычной отправки формы
}

$field = static fn(string $k): string => trim((string)($data[$k] ?? ''));

// Ловушка для ботов: поле спрятано от людей, заполнить его может только робот.
// Отвечаем «принято», чтобы спамер не подбирал обход.
if ($field('company') !== '') {
    echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE);
    exit;
}

$name  = $field('name');
$phone = $field('phone');
$car   = $field('car');
$msg   = $field('message');

if ($name === '' || $phone === '') {
    fail('нужны имя и телефон');
}
if (mb_strlen($name) > 100 || mb_strlen($phone) > 40
    || mb_strlen($car) > 200 || mb_strlen($msg) > 2000) {
    fail('слишком длинно');
}
// В телефоне оставляем только то, что бывает в телефоне.
if (!preg_match('/^[0-9+()\-\s]{6,40}$/u', $phone)) {
    fail('проверьте телефон');
}

// ---- Простое ограничение частоты ----------------------------------------
// Одна заявка в минуту с адреса: от случайного двойного нажатия и от ботов,
// которые прошли ловушку.
$ip  = (string)($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
$key = sys_get_temp_dir() . '/zayavka_' . md5($ip);
if (is_file($key) && (time() - (int)filemtime($key)) < 60) {
    fail('слишком часто, попробуйте через минуту', 429);
}
@touch($key);

// ---- Собираем текст ------------------------------------------------------
$lines = [
    'Заявка с сайта',
    'Имя: ' . $name,
    'Телефон: ' . $phone,
];
if ($car !== '') { $lines[] = 'Машина: ' . $car; }
if ($msg !== '') { $lines[] = 'Вопрос: ' . $msg; }
$lines[] = 'Время: ' . date('d.m.Y H:i');
$text = implode("\n", $lines);

$delivered = false;

// ---- 1. MAX --------------------------------------------------------------
// POST https://platform-api2.max.ru/messages?user_id=<id>
// Заголовок Authorization: <токен>. Токен выдаётся после модерации бота.
if (!empty($cfg['max_token']) && !empty($cfg['max_user_id'])) {
    $url = 'https://platform-api2.max.ru/messages?user_id=' . rawurlencode((string)$cfg['max_user_id']);
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_HTTPHEADER     => [
            'Authorization: ' . $cfg['max_token'],
            'Content-Type: application/json',
        ],
        CURLOPT_POSTFIELDS => json_encode(
            ['text' => $text, 'notify' => true],
            JSON_UNESCAPED_UNICODE
        ),
    ]);
    $body = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($code >= 200 && $code < 300) {
        $delivered = true;
    } else {
        // Не роняем заявку из-за мессенджера: остаётся почта.
        @error_log('MAX не принял заявку: HTTP ' . $code . ' ' . substr((string)$body, 0, 300));
    }
}

// ---- 2. Почта ------------------------------------------------------------
if (!empty($cfg['mail_to'])) {
    $subject = '=?UTF-8?B?' . base64_encode('Заявка с сайта — ' . $name) . '?=';
    $headers = implode("\r\n", [
        'From: ' . ($cfg['mail_from'] ?? ('no-reply@' . ($_SERVER['HTTP_HOST'] ?? 'localhost'))),
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: 8bit',
    ]);
    if (@mail($cfg['mail_to'], $subject, $text, $headers)) {
        $delivered = true;
    }
}

// ---- 3. Запасная копия на диск ------------------------------------------
// Чтобы ни одна заявка не пропала, даже если и мессенджер, и почта отказали.
$log = __DIR__ . '/zayavki.log';
@file_put_contents($log, $text . "\n---\n", FILE_APPEND | LOCK_EX);
@chmod($log, 0600);

if (!$delivered) {
    // Заявка сохранена, но ни один канал не сработал — честно говорим об этом,
    // чтобы человек позвонил, а не ждал звонка впустую.
    fail('заявка сохранена, но не доставлена — позвоните, пожалуйста', 502);
}

echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE);
