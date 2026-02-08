const { spawn } = require('child_process');
const path = require('path');

const isWindows = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');

const pythonPath = isWindows
  ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
  : path.join(backendDir, '.venv', 'bin', 'python');

const args = ['-m', 'uvicorn', 'main:app', '--reload', '--port', '8000'];

const child = spawn(pythonPath, args, {
  cwd: backendDir,
  stdio: 'inherit',
  shell: false
});

child.on('error', (err) => {
  console.error('Failed to start backend:', err.message);
  console.error('Make sure you have created the virtual environment:');
  console.error('  cd backend && python -m venv .venv && pip install -r requirements.txt');
  process.exit(1);
});

child.on('exit', (code) => process.exit(code || 0));
