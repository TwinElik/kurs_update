<?php
declare(strict_types=1);

use PhpAmqpLib\Connection\AMQPStreamConnection;
use PhpAmqpLib\Message\AMQPMessage;

$siteRoot = dirname(__DIR__, 2);
$configPath = getenv('OC_CONFIG_PATH') ?: $siteRoot . '/config.php';
$autoloadPath = getenv('AMQP_AUTOLOAD') ?: $siteRoot . '/vendor/autoload.php';

if (!is_file($configPath)) {
    fwrite(STDERR, "OpenCart config not found: {$configPath}\n");
    exit(1);
}

if (!is_file($autoloadPath)) {
    fwrite(STDERR, "Composer autoload not found: {$autoloadPath}\n");
    fwrite(STDERR, "Run: composer require php-amqplib/php-amqplib\n");
    exit(1);
}

require_once $configPath;
require_once $autoloadPath;

$rabbitHost = getenv('RABBITMQ_HOST') ?: '127.0.0.1';
$rabbitPort = (int)(getenv('RABBITMQ_PORT') ?: 5672);
$rabbitUser = getenv('RABBITMQ_USER') ?: 'jewelry_user';
$rabbitPassword = getenv('RABBITMQ_PASSWORD') ?: 'my_secure_password';
$rabbitVhost = getenv('RABBITMQ_VHOST') ?: '/';
$rabbitQueue = getenv('RABBITMQ_QUEUE') ?: 'gold_price_events';

$brand = 'diamant';
$tableName = 'diamant_gold_prices';
$requiredSamples = [375, 583, 585, 750, 850, 875, 916, 999];

function dbConnect(): mysqli
{
    $host = DB_HOSTNAME;
    $port = defined('DB_PORT') ? (int)DB_PORT : 3306;
    $user = DB_USERNAME;
    $password = DB_PASSWORD;
    $database = DB_DATABASE;

    $mysqli = new mysqli($host, $user, $password, $database, $port);
    if ($mysqli->connect_errno) {
        throw new RuntimeException('MySQL connect failed: ' . $mysqli->connect_error);
    }
    $mysqli->set_charset('utf8mb4');

    return $mysqli;
}

function ensureGoldPriceTable(mysqli $db, string $tableName): void
{
    $sql = "
        CREATE TABLE IF NOT EXISTS `{$tableName}` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `source_price_id` INT NOT NULL,
            `kurs` INT NOT NULL,
            `price_375_from` INT NOT NULL,
            `price_375_to` INT NOT NULL,
            `price_583_from` INT NOT NULL,
            `price_583_to` INT NOT NULL,
            `price_585_from` INT NOT NULL,
            `price_585_to` INT NOT NULL,
            `price_750_from` INT NOT NULL,
            `price_750_to` INT NOT NULL,
            `price_850_from` INT NOT NULL,
            `price_850_to` INT NOT NULL,
            `price_875_from` INT NOT NULL,
            `price_875_to` INT NOT NULL,
            `price_916_from` INT NOT NULL,
            `price_916_to` INT NOT NULL,
            `price_999_from` INT NOT NULL,
            `price_999_to` INT NOT NULL,
            `created_at` DATETIME NOT NULL,
            UNIQUE KEY `uq_source_price_id` (`source_price_id`),
            INDEX `idx_created_at` (`created_at`)
        )
    ";

    if (!$db->query($sql)) {
        throw new RuntimeException('Create table failed: ' . $db->error);
    }
}

function validatePayload(array $payload, string $brand, array $requiredSamples): array
{
    if (($payload['event'] ?? '') !== 'gold_price_updated') {
        throw new RuntimeException('Unsupported event');
    }

    if (empty($payload['generation_id'])) {
        throw new RuntimeException('generation_id is missing');
    }

    if (!isset($payload['kurs'])) {
        throw new RuntimeException('kurs is missing');
    }

    if (empty($payload['created_at'])) {
        throw new RuntimeException('created_at is missing');
    }

    if (empty($payload['brands'][$brand]) || !is_array($payload['brands'][$brand])) {
        throw new RuntimeException("Brand payload is missing: {$brand}");
    }

    $prices = $payload['brands'][$brand];
    foreach ($requiredSamples as $sample) {
        foreach (['from', 'to'] as $side) {
            $key = "{$sample}_{$side}";
            if (!isset($prices[$key])) {
                throw new RuntimeException("Price key is missing: {$key}");
            }
        }
    }

    return $prices;
}

function insertGoldPrice(mysqli $db, string $tableName, array $payload, array $prices, array $requiredSamples): void
{
    $columns = ['source_price_id', 'kurs'];
    $values = [(int)$payload['generation_id'], (int)$payload['kurs']];

    foreach ($requiredSamples as $sample) {
        $columns[] = "price_{$sample}_from";
        $values[] = (int)$prices["{$sample}_from"];
        $columns[] = "price_{$sample}_to";
        $values[] = (int)$prices["{$sample}_to"];
    }

    $columns[] = 'created_at';
    $values[] = (string)$payload['created_at'];

    $escapedColumns = array_map(static fn($column) => '`' . str_replace('`', '``', $column) . '`', $columns);
    $placeholders = implode(',', array_fill(0, count($values), '?'));
    $types = str_repeat('i', count($values) - 1) . 's';

    $sql = sprintf(
        'INSERT INTO `%s` (%s) VALUES (%s) ON DUPLICATE KEY UPDATE source_price_id = source_price_id',
        str_replace('`', '``', $tableName),
        implode(',', $escapedColumns),
        $placeholders
    );

    $stmt = $db->prepare($sql);
    if (!$stmt) {
        throw new RuntimeException('Prepare failed: ' . $db->error);
    }

    $stmt->bind_param($types, ...$values);
    if (!$stmt->execute()) {
        throw new RuntimeException('Insert failed: ' . $stmt->error);
    }
    $stmt->close();
}

function handleMessage(AMQPMessage $message, string $brand, string $tableName, array $requiredSamples): void
{
    $payload = json_decode($message->getBody(), true);
    if (!is_array($payload)) {
        throw new RuntimeException('Invalid JSON payload');
    }

    $prices = validatePayload($payload, $brand, $requiredSamples);

    $db = dbConnect();
    try {
        ensureGoldPriceTable($db, $tableName);
        insertGoldPrice($db, $tableName, $payload, $prices, $requiredSamples);
    } finally {
        $db->close();
    }
}

$connection = new AMQPStreamConnection(
    $rabbitHost,
    $rabbitPort,
    $rabbitUser,
    $rabbitPassword,
    $rabbitVhost,
    false,
    'AMQPLAIN',
    null,
    'en_US',
    3.0,
    60.0
);

$channel = $connection->channel();
$channel->queue_declare($rabbitQueue, false, true, false, false);
$channel->basic_qos(null, 1, null);

echo "Diamant gold price worker started. Queue: {$rabbitQueue}\n";

$channel->basic_consume(
    $rabbitQueue,
    '',
    false,
    false,
    false,
    false,
    function (AMQPMessage $message) use ($brand, $tableName, $requiredSamples): void {
        try {
            handleMessage($message, $brand, $tableName, $requiredSamples);
            $message->ack();
            echo date('Y-m-d H:i:s') . " synced message\n";
        } catch (Throwable $e) {
            fwrite(STDERR, date('Y-m-d H:i:s') . ' sync failed: ' . $e->getMessage() . "\n");
            $message->nack(false, true);
            sleep(5);
        }
    }
);

while ($channel->is_consuming()) {
    $channel->wait();
}

$channel->close();
$connection->close();
