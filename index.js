// Starts the Stage bot. Settings come from the environment, or from a .env
// file beside this one (see .env.example).

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { Config } = require('./src/config');
const { StageBot } = require('./src/stage-bot');
const { InstanceLock } = require('./src/instance-lock');

const envFile = path.join(__dirname, '.env');
if (fs.existsSync(envFile)) process.loadEnvFile(envFile);

const config = Config.fromEnv();
const missing = config.missing();
if (missing.length) {
  console.error(`Missing settings: ${missing.join(', ')}. Copy .env.example to .env and fill them in.`);
  process.exit(1);
}

const lock = new InstanceLock({ file: path.join(os.tmpdir(), 'bbpr-stage-bot.pid') });
const running = lock.acquire();
if (running) {
  console.error(`The bot is already running (process ${running}). Stop that one first.`);
  process.exit(1);
}
process.on('exit', () => lock.release());

const bot = new StageBot({ config });
let stopping = false;
const shutdown = async () => {
  if (stopping) return;
  stopping = true;
  console.info('Leaving the Stage...');
  await bot.stop().catch(() => {});
  process.exit(0);
};
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

bot.start().catch((err) => {
  console.error(`Could not log in to Discord: ${err.message}`);
  process.exit(1);
});
