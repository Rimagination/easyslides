/** npm pack builds a physical runtime; consumers install the prebuilt package without hooks. */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./build_npm_package.py', import.meta.url));
const commands = process.env.EASYSLIDES_PYTHON
  ? [[process.env.EASYSLIDES_PYTHON]]
  : process.platform === 'win32' ? [['python'], ['py', '-3'], ['python3']] : [['python3'], ['python']];

let launched = false;
for (const [command, ...prefix] of commands) {
  const result = spawnSync(command, [...prefix, '-X', 'utf8', script], { stdio: 'inherit' });
  if (result.error?.code === 'ENOENT') continue;
  launched = true;
  if (result.error) console.error(result.error.message);
  process.exitCode = result.status ?? 1;
  break;
}
if (!launched) {
  console.error('Building EasySlides requires Python 3.10+. Set EASYSLIDES_PYTHON to its executable path.');
  process.exitCode = 1;
}
