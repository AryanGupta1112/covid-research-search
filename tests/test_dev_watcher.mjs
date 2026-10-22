import assert from 'node:assert/strict';
import path from 'node:path';
import { createServer } from 'vite';

const server = await createServer({ logLevel: 'silent', server: { port: 0 } });
const watcherErrors = [];
server.watcher.on('error', error => watcherErrors.push(error));
try {
  await server.listen();
  const deadline = Date.now() + 5000;
  let watched;
  do {
    watched = server.watcher.getWatched();
    if (Object.entries(watched).some(([dir, files]) => dir.replaceAll('\\', '/').endsWith('/src') && files.includes('main.jsx'))) break;
    await new Promise(resolve => setTimeout(resolve, 25));
  } while (Date.now() < deadline);
  const files = Object.entries(watched).flatMap(([dir, names]) => names.map(name => path.join(dir, name).replaceAll('\\', '/')));
  assert.ok(files.some(file => file.endsWith('/src/main.jsx')), 'Frontend source must remain watched');
  const root = process.cwd().replaceAll('\\', '/') + '/';
  const generated = files.filter(file => file.startsWith(root)).map(file => file.slice(root.length))
    .filter(file => /^(artifacts|data|\.venv|venv|backend)\//.test(file) || /\.(docx|pptx|pdf)$/.test(file));
  assert.deepEqual(generated, [], 'Generated and Python files must not be watched');
  assert.deepEqual(watcherErrors, [], 'Watcher must not emit EBUSY or other errors');
  console.log('PASS Vite watches frontend sources and excludes generated artifacts and Python files');
} finally {
  await server.close();
}
