import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkTools, childEnvironment } from './dev.mjs';

test('MSVC selection is local to the child and preserves other settings', () => {
  const original = { PATH: 'tools', RUSTUP_TOOLCHAIN: 'gnu' };
  assert.equal(childEnvironment('win32', original).RUSTUP_TOOLCHAIN, 'stable-x86_64-pc-windows-msvc');
  assert.equal(original.RUSTUP_TOOLCHAIN, 'gnu');
  assert.equal(childEnvironment('darwin', original).RUSTUP_TOOLCHAIN, 'gnu');
});
test('doctor reports missing tools without claiming capture works', () => {
  const result = checkTools('win32', {}, () => ({status: 1}));
  assert.equal(result.length, 4);
  assert.ok(result.every(item => !item.ok && item.help));
});
test('mac doctor includes the native helper compiler', () => {
  const called = [];
  const result = checkTools('darwin', {FFMPEG_PATH:'/tools/ffmpeg'}, (exe,args) => {
    called.push([exe,args]); return {status: 0, stdout: ' T.C drawtext V->V Draw text on video.'};
  });
  assert.ok(result.every(item => item.ok));
  assert.ok(called.some(([exe]) => exe === 'xcrun'));
  assert.ok(called.some(([exe]) => exe === '/tools/ffmpeg'));
});

test('minimal FFmpeg is rejected before a recording can start', () => {
  const result = checkTools('darwin', {}, () => ({status: 0, stdout: ' ... scale V->V Scale video.'}));
  const text = result.find(item => item.name === 'FFmpeg text overlays');
  assert.equal(text.ok, false);
  assert.match(text.help, /ffmpeg-full/);
});

test('an unsuccessful filter probe cannot pass from partial output', () => {
  const result = checkTools('win32', {}, (_exe, args) => ({status: args.includes('-filters') ? 1 : 0, stdout: ' T.C drawtext V->V Draw text.'}));
  assert.equal(result.find(item => item.name === 'FFmpeg text overlays').ok, false);
});
