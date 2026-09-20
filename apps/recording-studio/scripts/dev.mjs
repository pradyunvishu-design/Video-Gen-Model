import { existsSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export function childEnvironment(platform, current) {
  return { ...current, ...(platform === 'win32' ? { RUSTUP_TOOLCHAIN: 'stable-x86_64-pc-windows-msvc' } : {}) };
}

export function checkTools(platform, env, run = spawnSync) {
  const checks = [
    ['Rust', 'rustc', ['--version'], 'Install Rust using rustup; Windows needs the MSVC toolchain.'],
    ['Cargo', 'cargo', ['--version'], 'Install Rust using rustup.'],
    ['FFmpeg', env.FFMPEG_PATH || 'ffmpeg', ['-version'], 'Install FFmpeg and put it on PATH, or set FFMPEG_PATH in .env.'],
    ['FFprobe', env.FFPROBE_PATH || 'ffprobe', ['-version'], 'Install FFprobe with FFmpeg, or set FFPROBE_PATH in .env.'],
  ];
  if (platform === 'darwin') checks.push(['Xcode tools', 'xcrun', ['--find', 'swiftc'], 'Install Xcode Command Line Tools.']);
  const results = checks.map(([name, executable, args, help]) => {
    const result = run(executable, args, { env, encoding: 'utf8', windowsHide: true, timeout: 120000 });
    return { name, ok: result.status === 0, help };
  });
  if (results.find(check => check.name === 'FFmpeg')?.ok) {
    const filters = run(env.FFMPEG_PATH || 'ffmpeg', ['-hide_banner', '-filters'], { env, encoding: 'utf8', windowsHide: true, timeout: 120000 });
    results.push({
      name: 'FFmpeg text overlays',
      ok: filters.status === 0 && /\bdrawtext\s+V->V\b/.test(`${filters.stdout || ''}\n${filters.stderr || ''}`),
      help: platform === 'darwin'
        ? 'Run brew install ffmpeg-full, then add its bin directory to PATH or set FFMPEG_PATH/FFPROBE_PATH in .env. The minimal Homebrew ffmpeg omits drawtext.'
        : 'Install a full FFmpeg build with drawtext support and set FFMPEG_PATH in .env if needed.',
    });
  }
  return results;
}

export async function main(args = process.argv.slice(2)) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  if (!['win32', 'darwin'].includes(process.platform)) throw new Error('Recording Studio v1 supports Windows and macOS only.');
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 16)) throw new Error('Install Node.js 22.16 or later.');
  if (existsSync(join(root, '.env'))) process.loadEnvFile(join(root, '.env'));
  const env = childEnvironment(process.platform, process.env);
  const checks = checkTools(process.platform, env);
  for (const check of checks) console.log(`${check.ok ? 'OK' : 'MISSING'} ${check.name}${check.ok ? '' : ': ' + check.help}`);
  if (checks.some(check => !check.ok)) throw new Error('Fix the prerequisites above and retry. Nothing was recorded.');
  if (args.includes('--doctor')) return;
  const cli = join(root, 'node_modules', '@tauri-apps', 'cli', 'tauri.js');
  if (!existsSync(cli)) {
    const npmCli = process.env.npm_execpath;
    if (!npmCli) throw new Error('Start with npm run dev so dependencies can be installed.');
    console.log('Installing locked application dependencies…');
    const install = spawnSync(process.execPath, [npmCli, 'ci'], { cwd: root, env, stdio: 'inherit', windowsHide: true });
    if (install.status !== 0) throw new Error('Dependency installation failed. Check the output and retry.');
  }
  const tauriArgs = args.includes('--build') ? ['build', '--no-bundle'] : ['dev'];
  const child = spawn(process.execPath, [cli, ...tauriArgs], { cwd: root, env, stdio: 'inherit', windowsHide: true });
  await new Promise((resolveDone, reject) => {
    child.on('error', reject);
    child.on('close', code => code === 0 ? resolveDone() : reject(new Error(`Desktop process exited with code ${code}.`)));
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
