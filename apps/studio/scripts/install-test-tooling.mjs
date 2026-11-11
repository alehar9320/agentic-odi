#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const studioDir = path.resolve(__dirname, '..');

const packages = [
  '@playwright/test@1.64.1',
  'playwright@^1.64.1',
  '@vitest/browser-playwright@^4.1.12',
  'vitest-browser-react@^2.3.0',
  'chromatic@^18.13.3',
  '@chromatic-com/vitest@^1.0.1',
  '@tauri-apps/cli@^2.12.3',
];

const args = ['install', '--no-save', ...packages];
const child = spawn('npm', args, { cwd: studioDir, stdio: 'inherit' });
child.on('close', (code) => {
  process.exit(code ?? 1);
});
