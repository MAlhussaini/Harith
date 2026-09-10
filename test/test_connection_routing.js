const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('templates/opensprinkler_harith_controller.html', 'utf8');
const start = html.indexOf('function $(id)');
const end = html.indexOf('/* ================= Demo simulator', start);
assert.ok(start >= 0 && end > start, 'connection helper block not found');

const context = {
  URL,
  URLSearchParams,
  location: {
    protocol: 'https:',
    origin: 'https://harith.onrender.com',
  },
  navigator: {},
  document: {getElementById() { return null; }},
  setTimeout,
  clearTimeout,
};
vm.createContext(context);
vm.runInContext(html.slice(start, end), context);

function request(host) {
  return context.buildApiRequest('/jn', {}, '', host);
}

for (const host of [
  'http://10.56.215.106',
  'http://172.16.0.1',
  'http://172.31.255.254',
  'http://192.168.100.30',
  'http://100.109.102.8',
  'http://169.254.1.1',
  'http://router.local',
  'http://Harith',
]) {
  const result = request(host);
  assert.equal(result.direct, true, `${host} should use a direct request`);
  assert.equal(result.addressSpace, 'local');
  assert.equal(result.options.targetAddressSpace, 'local');
}

const loopback = request('http://127.0.0.1:8080');
assert.equal(loopback.direct, true);
assert.equal(loopback.addressSpace, 'loopback');
assert.equal(loopback.options.targetAddressSpace, undefined);

const publicRequest = request('https://controller.example.com:8443');
assert.equal(publicRequest.direct, false);
assert.ok(publicRequest.url.startsWith('https://harith.onrender.com/os/proxy?'));
assert.ok(publicRequest.url.includes('_host=https%3A%2F%2Fcontroller.example.com%3A8443'));

const withPort = request('10.56.215.106:81');
assert.ok(withPort.url.startsWith('http://10.56.215.106:81/jn?'));

assert.throws(() => request('ftp://10.56.215.106'), /invalidHost/);
assert.throws(() => request('http://user:pass@10.56.215.106'), /invalidHost/);

const buildStationsStart = html.indexOf('function buildStations');
const buildStationsEnd = html.indexOf('function savePrefs', buildStationsStart);
assert.ok(buildStationsStart >= 0 && buildStationsEnd > buildStationsStart);
vm.runInContext(html.slice(buildStationsStart, buildStationsEnd), context);
context.stations = [];
context.buildStations({
  dname: 'Harith',
  snames: ['S01', 'S02'],
  stn_dis: [0],
});
assert.equal(context.stations.length, 2, 'device display name must not affect login');

async function testApiErrors() {
  let currentHost = 'http://10.56.215.106';
  const elements = {
    'cfg-host': {value: currentHost},
    'cfg-pw': {value: 'secret'},
    'cfg-ignore-pw': {checked: false},
  };
  context.document.getElementById = id => elements[id] || null;
  context.md5 = () => 'test-hash';
  context.demoMode = false;

  context.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({result: 2}),
  });
  await assert.rejects(
    context.apiGet('/jn'),
    error => error && error.code === 'unauthorized',
  );

  context.navigator.permissions = {
    query: async () => ({state: 'denied'}),
  };
  context.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(
    context.apiGet('/jn'),
    error => error && error.code === 'localPermissionDenied',
  );

  currentHost = 'https://controller.example.com';
  elements['cfg-host'].value = currentHost;
  context.fetch = async () => ({
    ok: false,
    status: 502,
    json: async () => ({error: 'upstream timeout'}),
  });
  await assert.rejects(
    context.apiGet('/jn'),
    error => error && error.code === 'proxyNetworkFail',
  );
}

testApiErrors()
  .then(() => console.log('connection routing and error tests passed'))
  .catch(error => {
    console.error(error);
    process.exitCode = 1;
  });
